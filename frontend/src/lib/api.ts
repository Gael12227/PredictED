import type { ContextKey, CsvSummary, HistoryPoint, WhatIfResp } from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  summary(context: ContextKey, hospitalType: string): Promise<CsvSummary> {
    return req(
      `/api/context/${context}/summary?hospital_type=${encodeURIComponent(hospitalType)}`
    );
  },
  history(context: ContextKey, hospitalType: string, months = 60): Promise<{ hospital_type: string; points: HistoryPoint[] }> {
    return req(
      `/api/context/${context}/history?hospital_type=${encodeURIComponent(
        hospitalType
      )}&months=${months}`
    );
  },
  whatif(hospitalType: string, features: Record<string, number>): Promise<WhatIfResp> {
    return req(`/api/whatif`, {
      method: "POST",
      body: JSON.stringify({ hospital_type: hospitalType, features }),
    });
  },
  applyOverride(hospitalType: string, features: Record<string, number>) {
    return req(`/api/state/override`, {
      method: "POST",
      body: JSON.stringify({ hospital_type: hospitalType, features }),
    });
  },
  clearOverride(hospitalType: string) {
    return req(`/api/state/override?hospital_type=${encodeURIComponent(hospitalType)}`, {
      method: "DELETE",
    });
  },
};
