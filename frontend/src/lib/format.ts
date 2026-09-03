export function fmt(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

export function fmtPct(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `${fmt(n, 0)}%`;
}

export function fmtSigned(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined) return "—";
  const s = n > 0 ? "+" : "";
  return `${s}${fmt(n, digits)}`;
}

export function fmtAge(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "offline";
  if (seconds < 3) return "now";
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

export function clock(epochSeconds?: number): string {
  const d = epochSeconds ? new Date(epochSeconds * 1000) : new Date();
  return d.toLocaleTimeString("en-US", { hour12: false });
}

export function levelIndex(level: string): number {
  return ["not_busy", "busy", "overcrowded", "critical"].indexOf(level);
}

export const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n));
