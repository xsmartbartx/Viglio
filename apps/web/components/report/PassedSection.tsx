import type { ReportFindingResponse } from "../../lib/types";

export function PassedSection({ findings }: { findings: ReportFindingResponse[] }) {
  const passed = findings.filter((finding) => finding.verdict === "passed");
  if (passed.length === 0) return null;

  return (
    <details className="mt-8 border-t border-black/10 dark:border-white/10 pt-6 text-sm">
      <summary className="cursor-pointer select-none font-semibold uppercase tracking-wide text-black/50 dark:text-white/50">
        Passed ({passed.length})
      </summary>
      <ul className="mt-2 space-y-1">
        {passed.map((finding) => (
          <li key={finding.fingerprint} className="text-black/70 dark:text-white/70">
            {finding.title}
          </li>
        ))}
      </ul>
    </details>
  );
}
