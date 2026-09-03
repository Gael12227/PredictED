"""Delhi ED CSVs → per-archetype context.

Loads ``Delhi_urban.csv`` / ``delhi_Rural.csv`` once at startup and exposes:
  - the hospital archetypes found in each file (Big/Small …)
  - typical monthly NEDOCS + occupancy baselines
  - typical NEDOCS per AQI bucket, top chief complaints, weather mix
  - monthly history series for the trend chart
  - typical census medians (used for "driver vs typical" analysis)

The two files have different column schemas (urban is tourist-season framed,
rural is agricultural-season framed) — a small adapter maps both to the same
feature vocabulary.
"""
from __future__ import annotations

import pandas as pd

from ..config import settings

URBAN_FILE = settings.csv_urban
RURAL_FILE = settings.csv_rural

# urban CSV → feature vocabulary
URBAN_MAP = {
    "ed_pts": "NEDOCS_Param_3_ED_Patients_Count",
    "ed_beds": "NEDOCS_Param_1_ED_Total_Beds",
    "hosp_beds": "NEDOCS_Param_2_Hospital_Total_Beds",
    "admits": "NEDOCS_Param_4_Patients_Waiting_Admit",
    "vents": "NEDOCS_Param_7_ED_Respirators_In_Use",
    "longest_wait_min": "NEDOCS_Param_5_Longest_Wait_Minutes",
}
# rural CSV → feature vocabulary
RURAL_MAP = {
    "ed_pts": "Total_Patients_in_ED",
    "ed_beds": "ED_Total_Beds",
    "hosp_beds": "Hospital_Total_Beds",
    "admits": "Admitted_Patients_Waiting_in_ED",
    "vents": "ED_Respirators_in_Use",
    "longest_wait_min": "Longest_Admit_Wait_Time_Minutes",
}

NEDOCS_COL = "NEDOCS_Total_Score"
OCC_COL = "Bed_Occupancy_Rate_%"
AQI_COL = "Air_Quality_Index_AQI"
COMPLAINT_COL = "Dominant_Chief_Complaint"
WEATHER_COL = "Weather"
HOSPITAL_COL = "Hospital_Type"
DATE_COL = "Date"
MONTH_COL = "Simulated_Month"


def _parse_date(s: pd.Series) -> pd.Series:
    # Formats differ between the files (1/1/1996 vs 1996-01-01).
    try:
        return pd.to_datetime(s, format="mixed", dayfirst=False, errors="coerce")
    except TypeError:  # older pandas
        return pd.to_datetime(s, errors="coerce")


class CsvContext:
    """Aggregated context for one dataset file (urban or rural)."""

    def __init__(self, context: str, path: pd.Path | str, colmap: dict):
        self.context = context
        self.colmap = colmap
        self.df = pd.read_csv(path)
        self.df[DATE_COL] = _parse_date(self.df[DATE_COL].astype(str))
        # Some rows may have empty year/months — keep what we can
        self.df = self.df.dropna(subset=[NEDOCS_COL]).copy()
        if MONTH_COL in self.df.columns:
            self.df["month_idx"] = self.df[MONTH_COL].astype(int)
        else:
            self.df["month_idx"] = self.df[DATE_COL].dt.month.fillna(1).astype(int)
        self.archetypes: dict[str, dict] = self._build_archetypes()

    # ------------------------------------------------------------- helpers
    def _feat_cols(self) -> dict:
        out = dict(self.colmap)
        # waits are in minutes in the CSV → convert to hours at use site
        return out

    def _archetype_names(self) -> list[str]:
        return sorted(self.df[HOSPITAL_COL].dropna().unique().tolist())

    def _rows(self, hospital_type: str) -> pd.DataFrame:
        return self.df[self.df[HOSPITAL_COL] == hospital_type]

    @staticmethod
    def _median(df: pd.DataFrame, col: str):
        if col not in df.columns:
            return None
        v = pd.to_numeric(df[col], errors="coerce")
        v = v.dropna()
        if v.empty:
            return None
        return float(v.median())

    # ------------------------------------------------------------- build
    def _build_archetypes(self) -> dict[str, dict]:
        out = {}
        for name in self._archetype_names():
            rows = self._rows(name)
            beds = self._median(rows, self.colmap["ed_beds"]) or 0
            hosp = self._median(rows, self.colmap["hosp_beds"]) or 0
            lw_min = self._median(rows, self.colmap["longest_wait_min"])
            out[name] = {
                "hospital_type": name,
                "rows": len(rows),
                "typical_census": {
                    "ed_pts": self._median(rows, self.colmap["ed_pts"]),
                    "ed_beds": beds,
                    "admits": self._median(rows, self.colmap["admits"]),
                    "hosp_beds": hosp,
                    "vents": self._median(rows, self.colmap["vents"]),
                    "longest_wait": (lw_min / 60.0) if lw_min is not None else None,
                    "last_wait": None,  # not present in CSV; infer below
                },
                "monthly": self._monthly(rows),
                "aqi_bins": self._aqi_bins(rows),
                "complaints": self._complaints(rows),
                "weather": self._weather_mix(rows),
                "global": {
                    "mean": self._median(rows, NEDOCS_COL),
                    "p90": self._p90(rows, NEDOCS_COL),
                    "occ_mean": self._median(rows, OCC_COL),
                },
            }
        return out

    @staticmethod
    def _p90(df: pd.DataFrame, col: str) -> float | None:
        if col not in df.columns:
            return None
        v = pd.to_numeric(df[col], errors="coerce").dropna()
        if v.empty:
            return None
        return float(v.quantile(0.90))

    def _monthly(self, df: pd.DataFrame) -> dict[int, dict]:
        out = {}
        g = df.groupby("month_idx")
        for month, sub in g:
            n = pd.to_numeric(sub[NEDOCS_COL], errors="coerce").dropna()
            occ = (
                pd.to_numeric(sub[OCC_COL], errors="coerce").dropna()
                if OCC_COL in sub.columns
                else None
            )
            if n.empty:
                continue
            out[int(month)] = {
                "count": int(len(sub)),
                "mean": round(float(n.mean()), 1),
                "median": round(float(n.median()), 1),
                "p90": round(float(n.quantile(0.90)), 1),
                "occ": round(float(occ.mean()), 1) if occ is not None and len(occ) else None,
            }
        return out

    def _aqi_bins(self, df: pd.DataFrame) -> dict[str, dict]:
        if AQI_COL not in df.columns:
            return {}
        aqi = pd.to_numeric(df[AQI_COL], errors="coerce")
        labels = ["<50", "50-100", "100-150", "150-200", ">200"]
        edges = [-1, 50, 100, 150, 200, 1e9]
        out = {}
        for i, lab in enumerate(labels):
            mask = (aqi > edges[i]) & (aqi <= edges[i + 1])
            sub = df[mask]
            n = pd.to_numeric(sub[NEDOCS_COL], errors="coerce").dropna()
            if n.empty:
                continue
            out[lab] = {
                "count": int(len(sub)),
                "mean": round(float(n.mean()), 1),
            }
        return out

    def _complaints(self, df: pd.DataFrame) -> list[dict]:
        if COMPLAINT_COL not in df.columns:
            return []
        counts = df[COMPLAINT_COL].value_counts().head(6)
        out = []
        for label, cnt in counts.items():
            sub = df[df[COMPLAINT_COL] == label]
            n = pd.to_numeric(sub[NEDOCS_COL], errors="coerce").dropna()
            out.append({
                "complaint": str(label),
                "share_pct": round(100 * cnt / max(len(df), 1), 1),
                "mean_nedocs": round(float(n.mean()), 1) if len(n) else None,
            })
        return out

    def _weather_mix(self, df: pd.DataFrame) -> list[dict]:
        if WEATHER_COL not in df.columns:
            return []
        out = []
        for label, cnt in df[WEATHER_COL].value_counts().head(4).items():
            out.append({"weather": str(label), "days": int(cnt)})
        return out

    # ------------------------------------------------------------- queries
    def summary(self, hospital_type: str, month: int | None = None) -> dict:
        arch = self.archetypes.get(hospital_type)
        if arch is None:
            return {}
        month = int(month) if month is not None else None
        monthly = arch["monthly"].get(month, {}) if month else {}
        return {
            "hospital_type": hospital_type,
            "context": self.context,
            "rows": arch["rows"],
            "typical_census": arch["typical_census"],
            "global": arch["global"],
            "month": month,
            "monthly": monthly,
            "aqi_bins": arch["aqi_bins"],
            "complaints": arch["complaints"][:3],
            "weather": arch["weather"],
        }

    def history(self, hospital_type: str, months: int = 36) -> list[dict]:
        arch = self.archetypes.get(hospital_type)
        if arch is None:
            return []
        df = self._rows(hospital_type).copy()
        df["ym"] = (
            df[DATE_COL].dt.to_period("M").astype(str)
        ) if df[DATE_COL].notna().any() else None
        if df["ym"].isna().all():
            return []
        g = (
            df.groupby("ym")
            .agg(
                nedocs=pd.NamedAgg(column=NEDOCS_COL, aggfunc="mean"),
                occ=pd.NamedAgg(column=OCC_COL, aggfunc="mean"),
            )
            .reset_index()
        )
        g = g.sort_values("ym").tail(int(months))
        return [
            {
                "ym": row["ym"],
                "nedocs": round(float(row["nedocs"]), 1),
                "occ": round(float(row["occ"]), 1),
            }
            for _, row in g.iterrows()
        ]


def _load_contexts() -> dict[str, CsvContext]:
    return {
        "urban": CsvContext("urban", URBAN_FILE, URBAN_MAP),
        "rural": CsvContext("rural", RURAL_FILE, RURAL_MAP),
    }


CONTEXTS: dict[str, CsvContext] = {}


def load() -> dict[str, CsvContext]:
    """Idempotent startup load; returns the shared cache."""
    global CONTEXTS
    if not CONTEXTS:
        CONTEXTS = _load_contexts()
    return CONTEXTS


def get(context: str) -> CsvContext | None:
    return CONTEXTS.get(context)


def archetypes_for(context: str) -> list[str]:
    ctx = CONTEXTS.get(context)
    return sorted(ctx.archetypes) if ctx else []
