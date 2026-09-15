import type { ReportFindingResponse } from "../../lib/types";

function SkippedList({ findings }: { findings: ReportFindingResponse[] }) {
  return (
    <ul className="mt-2 space-y-1.5">
      {findings.map((finding) => (
        <li key={finding.fingerprint} className="flex items-baseline gap-2 text-sm">
          <span className="font-medium">{finding.title}</span>
          <span className="text-black/50 dark:text-white/50">— {finding.summary}</span>
        </li>
      ))}
    </ul>
  );
}

export function SkippedSection({ findings }: { findings: ReportFindingResponse[] }) {
  const inconclusive = findings.filter((finding) => finding.verdict === "inconclusive");
  const notApplicable = findings.filter((finding) => finding.verdict === "not_applicable");

  if (inconclusive.length === 0 && notApplicable.length === 0) {
    return null;
  }

  return (
    <div className="mt-8 space-y-6 border-t border-black/10 dark:border-white/10 pt-6">
      {inconclusive.length > 0 ? (
        <details className="text-sm">
          <summary className="cursor-pointer select-none font-semibold uppercase tracking-wide text-black/50 dark:text-white/50">
            Couldn&apos;t check ({inconclusive.length})
          </summary>
          <p className="mt-1 text-xs text-black/50 dark:text-white/50 max-w-prose">
            These checks didn&apos;t produce a clear pass or fail — usually because the target didn&apos;t
            respond the way the check expected. They don&apos;t count against the score.
          </p>
          <SkippedList findings={inconclusive} />
        </details>
      ) : null}

      {notApplicable.length > 0 ? (
        <details className="text-sm">
          <summary className="cursor-pointer select-none font-semibold uppercase tracking-wide text-black/50 dark:text-white/50">
            Not applicable ({notApplicable.length})
          </summary>
          <p className="mt-1 text-xs text-black/50 dark:text-white/50 max-w-prose">
            These checks don&apos;t apply to this site — for example, a check for a technology the site
            doesn&apos;t use. They don&apos;t count against the score.
          </p>
          <SkippedList findings={notApplicable} />
        </details>
      ) : null}
    </div>
  );
}
