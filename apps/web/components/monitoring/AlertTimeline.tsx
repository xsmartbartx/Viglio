import type { AlertResponse, AlertType } from "../../lib/types";

const LABEL_BY_TYPE: Record<AlertType, string> = {
  new_critical: "New critical finding",
  new_high: "New high-severity finding",
  regressed: "Previously fixed issue reappeared",
  cert_expiry: "TLS certificate expiring soon",
  score_drop: "Score dropped",
  scan_failed: "Scheduled scan failed",
};

const COLOR_BY_TYPE: Record<AlertType, string> = {
  new_critical: "text-severity-critical",
  new_high: "text-severity-high",
  regressed: "text-severity-high",
  cert_expiry: "text-severity-medium",
  score_drop: "text-severity-medium",
  scan_failed: "text-black/60 dark:text-white/60",
};

export function AlertTimeline({ alerts }: { alerts: AlertResponse[] }) {
  return (
    <div className="rounded-lg border border-black/10 dark:border-white/10 p-4">
      <p className="text-sm font-semibold mb-2">Recent alerts</p>
      {alerts.length === 0 ? (
        <p className="text-sm text-black/50 dark:text-white/50">
          No alerts yet — monitoring hasn&apos;t detected any changes.
        </p>
      ) : (
        <ul className="space-y-2">
          {alerts.map((alert) => (
            <li key={alert.alert_id} className="text-sm flex items-baseline justify-between gap-4">
              <span className={COLOR_BY_TYPE[alert.type] ?? ""}>
                {LABEL_BY_TYPE[alert.type] ?? alert.type}
                {alert.fingerprint ? ` (${alert.fingerprint})` : ""}
              </span>
              <span className="text-xs text-black/50 dark:text-white/50 whitespace-nowrap">
                {new Date(alert.created_at).toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
