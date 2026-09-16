"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api, ApiError } from "../../lib/api";
import type { EntitlementsResponse, MonitorResponse } from "../../lib/types";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

function defaultCadence(frequency: string | null): number {
  return frequency === "weekly" ? 168 : 24;
}

export function MonitorPanel({
  targetId,
  initialMonitor,
  entitlements,
}: {
  targetId: string;
  initialMonitor: MonitorResponse | null;
  entitlements: EntitlementsResponse;
}) {
  const { getToken } = useAuth();
  const [monitor, setMonitor] = useState<MonitorResponse | null>(initialMonitor);
  const [cadenceHours, setCadenceHours] = useState(
    initialMonitor?.cadence_hours ?? defaultCadence(entitlements.monitoring_frequency),
  );
  const [quietStart, setQuietStart] = useState<string>(
    initialMonitor?.quiet_start_utc?.toString() ?? "",
  );
  const [quietEnd, setQuietEnd] = useState<string>(
    initialMonitor?.quiet_end_utc?.toString() ?? "",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const monitoringAllowed = entitlements.monitoring_frequency !== null;
  const cadenceOptions =
    entitlements.monitoring_frequency === "weekly"
      ? [{ value: 168, label: "Weekly" }]
      : entitlements.monitoring_frequency === "daily+custom"
        ? [
            { value: 24, label: "Daily" },
            { value: 12, label: "Every 12 hours" },
            { value: 168, label: "Weekly" },
          ]
        : [];

  async function handleEnable() {
    setError(null);
    setBusy(true);
    try {
      const token = await getToken({ template: JWT_TEMPLATE });
      if (!token) throw new ApiError(401, null);
      const result = await api.createTargetMonitor(targetId, token, {
        cadence_hours: cadenceHours,
        quiet_start_utc: quietStart === "" ? null : Number(quietStart),
        quiet_end_utc: quietEnd === "" ? null : Number(quietEnd),
      });
      setMonitor(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't enable monitoring.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDisable() {
    if (!monitor) return;
    setError(null);
    setBusy(true);
    try {
      const token = await getToken({ template: JWT_TEMPLATE });
      if (!token) throw new ApiError(401, null);
      const result = await api.disableMonitor(monitor.monitor_id, token);
      setMonitor(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't disable monitoring.");
    } finally {
      setBusy(false);
    }
  }

  if (!monitoringAllowed) {
    return (
      <div className="rounded-lg border border-black/10 dark:border-white/10 p-4 text-sm">
        <p className="font-semibold">Monitoring</p>
        <p className="mt-1 text-black/60 dark:text-white/60">
          Scheduled re-scans aren&apos;t included in the current plan.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-black/10 dark:border-white/10 p-4 text-sm space-y-3">
      <div className="flex items-center justify-between">
        <p className="font-semibold">Monitoring</p>
        {monitor?.enabled ? (
          <span className="text-xs text-severity-pass">Active</span>
        ) : (
          <span className="text-xs text-black/50 dark:text-white/50">Off</span>
        )}
      </div>

      {monitor?.enabled ? (
        <>
          <p className="text-black/60 dark:text-white/60">
            Next scheduled scan: {new Date(monitor.next_run_at).toLocaleString()}
          </p>
          <button
            type="button"
            onClick={handleDisable}
            disabled={busy}
            className="rounded-md border border-black/10 dark:border-white/20 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
          >
            {busy ? "Working…" : "Turn off monitoring"}
          </button>
        </>
      ) : (
        <>
          <label className="block text-xs text-black/60 dark:text-white/60">
            Cadence
            <select
              value={cadenceHours}
              onChange={(e) => setCadenceHours(Number(e.target.value))}
              className="mt-1 block w-full rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm"
            >
              {cadenceOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <div className="grid grid-cols-2 gap-2">
            <label className="block text-xs text-black/60 dark:text-white/60">
              Quiet hours start (UTC)
              <input
                type="number"
                min={0}
                max={23}
                value={quietStart}
                onChange={(e) => setQuietStart(e.target.value)}
                placeholder="none"
                className="mt-1 block w-full rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm"
              />
            </label>
            <label className="block text-xs text-black/60 dark:text-white/60">
              Quiet hours end (UTC)
              <input
                type="number"
                min={0}
                max={23}
                value={quietEnd}
                onChange={(e) => setQuietEnd(e.target.value)}
                placeholder="none"
                className="mt-1 block w-full rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm"
              />
            </label>
          </div>

          <button
            type="button"
            onClick={handleEnable}
            disabled={busy}
            className="rounded-md bg-brand-primary px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
          >
            {busy ? "Working…" : "Turn on monitoring"}
          </button>
        </>
      )}

      {error ? <p className="text-xs text-severity-critical">{error}</p> : null}
    </div>
  );
}
