import type { ReportFindingResponse, Severity } from "../../lib/types";
import { FindingCard } from "./FindingCard";

const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

const SEVERITY_LABEL: Record<string, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

export function SeverityGroup({
  findings,
  printMode = false,
}: {
  findings: ReportFindingResponse[];
  printMode?: boolean;
}) {
  const failed = findings.filter((finding) => finding.verdict === "failed");

  if (failed.length === 0) {
    return (
      <div className="rounded-lg border border-severity-pass/30 bg-severity-pass/5 p-4 text-sm">
        No failed checks — nice work.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {SEVERITY_ORDER.map((severity) => {
        const group = failed.filter((finding) => finding.severity === severity);
        if (group.length === 0) return null;

        return (
          <section key={severity}>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-black/50 dark:text-white/50">
              {SEVERITY_LABEL[severity]} ({group.length})
            </h2>
            <div className="mt-2 space-y-3">
              {group.map((finding) => (
                <FindingCard key={finding.fingerprint} finding={finding} printMode={printMode} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
