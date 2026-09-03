export type LevelKey = "not_busy" | "busy" | "overcrowded" | "critical";
export type ContextKey = "urban" | "rural";

export const LEVEL_ORDER: LevelKey[] = ["not_busy", "busy", "overcrowded", "critical"];

export interface LevelStyle {
  key: LevelKey;
  label: string;
  color: string; // strong accent
  soft: string; // tinted background
  bar: string;
}

export const LEVEL_STYLES: Record<LevelKey, LevelStyle> = {
  not_busy: { key: "not_busy", label: "Not busy", color: "#15803d", soft: "#e8f6ec", bar: "#22c55e" },
  busy: { key: "busy", label: "Busy", color: "#b45309", soft: "#fdf1dd", bar: "#f59e0b" },
  overcrowded: { key: "overcrowded", label: "Overcrowded", color: "#c2410c", soft: "#fdece2", bar: "#f97316" },
  critical: { key: "critical", label: "Critical", color: "#b91c1c", soft: "#fde8e8", bar: "#ef4444" },
};

export interface Term {
  key: string;
  label: string;
  points: number;
}

export interface Factor {
  text: string;
  tag: string;
  severity: string;
  score_contribution?: string;
}

export interface Driver {
  feature: string;
  label: string;
  tag: string;
  weight: number;
  deviation: number;
  strength: number;
}

export interface FeatureVal {
  value: number | null;
  unit: string;
}

export interface ForecastBlock {
  score_2h: number;
  level: LevelKey;
  level_label: string;
}

export interface ExplanationBlock {
  score: number;
  level: LevelKey;
  level_label: string;
  summary: string;
  factors: Factor[];
  actions: string[];
  terms: Term[];
  forecast: ForecastBlock;
  drivers: Driver[];
  context_note: string;
  environment_note: string;
}

export interface Archetype {
  id: string;
  context: ContextKey;
  hospital_type: string;
  mode: string;
  overridden: boolean;
  override_fields: string[];
  features: Record<string, FeatureVal>;
  hardware: {
    ambient_noise_db: FeatureVal;
    arrival_velocity: FeatureVal;
    equipment_chaos_index: FeatureVal;
  };
  staleness_s: Record<string, number | null>;
  last_census_age_s: number;
  last_sensor_age_s: number;
  score: number;
  level: LevelKey;
  level_label: string;
  summary: string;
  factors: Factor[];
  actions: string[];
  terms: Term[];
  forecast: ForecastBlock;
  drivers: Driver[];
  context_note: string;
  environment_note: string;
  csv: {
    hospital_type: string;
    rows: number | null;
    typical_census: Record<string, number | null> | null;
    month_median: number | null;
    month_count: number | null;
    global_mean: number | null;
    global_p90: number | null;
  };
  trend_tail: { t: number; now: number; f2h: number }[];
}

export interface WebNote {
  ok: boolean;
  error?: string | null;
  fetched_at?: number | null;
  temperature_c?: number | null;
  humidity_pct?: number | null;
  wind_kmh?: number | null;
  weather_text?: string | null;
  aqi?: number | null;
  aqi_category?: string | null;
  pm2_5?: number | null;
}

export interface SourcesState {
  mqtt: { enabled: boolean; connected: boolean; error?: string | null; last_message_age_s?: number | null };
  demo: { active: boolean; mode: string };
  web: WebNote;
  db: { hardware_logs: number; emr_snapshots: number };
  csv: { urban_rows: number; rural_rows: number };
  uptime_s: number;
}

export interface ContextPayload {
  context: ContextKey;
  month: number;
  csv_loaded: boolean;
  web: WebNote;
  archetypes: Archetype[];
}

export interface FullPayload {
  generated_at: number;
  contexts: Record<ContextKey, ContextPayload>;
  sources: SourcesState;
}

export interface CsvSummary {
  hospital_type: string;
  context: ContextKey;
  rows: number;
  typical_census: Record<string, number | null>;
  global: { mean: number | null; p90: number | null; occ_mean: number | null };
  month: number;
  monthly: { count: number; mean: number; median: number; p90: number; occ: number | null } | null;
  aqi_bins: Record<string, { count: number; mean: number }>;
  complaints: { complaint: string; share_pct: number; mean_nedocs: number | null }[];
  weather: { weather: string; days: number }[];
}

export interface HistoryPoint {
  ym: string;
  nedocs: number;
  occ: number;
}

export interface WhatIfSensitivity {
  feature: string;
  label: string;
  unit: string;
  step: number;
  tag: string;
  delta_now: number | null;
  delta_2h: number | null;
}

export interface WhatIfResp {
  hospital_type: string;
  score: number;
  level: LevelKey;
  level_label: string;
  crossing: { direction: "up" | "down"; from: string; to: string } | null;
  sensitivity: WhatIfSensitivity[];
  explanation: ExplanationBlock;
}

// Static feature registry — must mirror backend/core/predictor.FEATURE_META
export const FEATURE_ORDER = [
  "ed_pts",
  "ed_beds",
  "admits",
  "hosp_beds",
  "vents",
  "longest_wait",
  "last_wait",
  "arrival_velocity",
  "equipment_chaos_index",
] as const;

export type FeatureKey = (typeof FEATURE_ORDER)[number];

export interface FeatureMeta {
  label: string;
  unit: string;
  step: number;
  tag: string;
  help: string;
}

export const FEATURE_META: Record<FeatureKey, FeatureMeta> = {
  ed_pts: { label: "ED patients", unit: "pts", step: 1, tag: "CENSUS", help: "Patients currently in the Emergency Department" },
  ed_beds: { label: "ED beds", unit: "beds", step: 1, tag: "CENSUS", help: "Licensed ED treatment beds" },
  admits: { label: "Admitted patients waiting", unit: "pts", step: 1, tag: "CENSUS", help: "Admitted patients boarded in the ED awaiting an inpatient bed" },
  hosp_beds: { label: "Hospital beds", unit: "beds", step: 1, tag: "CENSUS", help: "Total inpatient hospital bed capacity" },
  vents: { label: "Patients on ventilators", unit: "pts", step: 1, tag: "CENSUS", help: "ED patients requiring ventilatory support" },
  longest_wait: { label: "Longest admit wait", unit: "h", step: 0.25, tag: "FLOW", help: "Longest wait (hours) for an admitted ED patient" },
  last_wait: { label: "Last patient wait", unit: "h", step: 0.25, tag: "FLOW", help: "Wait (hours) of the most recently seen ED patient" },
  arrival_velocity: { label: "Arrival velocity", unit: "pts/min", step: 0.05, tag: "HARDWARE", help: "Ultrasound-inflow triggers per minute (15-min window)" },
  equipment_chaos_index: { label: "Movement chaos (IMU)", unit: "0-10", step: 0.5, tag: "HARDWARE", help: "Equipment/patient movement intensity from IMU variance" },
};

export const TAG_LABELS: Record<string, string> = {
  CENSUS: "Census",
  FLOW: "Flow",
  HARDWARE: "Hardware",
  ENVIRONMENT: "Environment",
  ACUITY: "Acuity",
};
