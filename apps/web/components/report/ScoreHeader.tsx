import type { ScanReportResponse } from "../../lib/types";

const GRADE_COLOR: Record<string, string> = {
  A: "text-severity-pass",
  B: "text-severity-pass",
  C: "text-severity-medium",
  D: "text-severity-high",
  F: "text-severity-critical",
};

export function ScoreHeader({ report }: { report: ScanReportResponse }) {
  const gradeColor = GRADE_COLOR[report.grade] ?? "text-severity-critical";

  return (
    <div className="border-b border-black/10 dark:border-white/10 pb-6 mb-6">
      <p className="text-sm text-black/60 dark:text-white/60 break-all">{report.target_origin}</p>
      <div className="flex items-baseline gap-4 mt-1">
        <span className={`text-5xl font-bold ${gradeColor}`}>{report.grade}</span>
        <span className="text-2xl">{report.score.toFixed(0)} / 100</span>
      </div>
      <p className="text-xs text-black/50 dark:text-white/50 mt-2">
        Scanned {new Date(report.generated_at).toLocaleString()} · registry {report.registry_version}
      </p>
      <p className="text-xs text-black/40 dark:text-white/40 mt-4 max-w-prose">
        This is an automated assessment, not a certification, and reflects the target&apos;s state
        at the scan timestamp under the registry version above.
      </p>
    </div>
  );
}
