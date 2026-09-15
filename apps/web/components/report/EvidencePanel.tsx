import type { EvidenceResponse } from "../../lib/types";

export function EvidencePanel({
  evidence,
  defaultOpen = false,
}: {
  evidence: EvidenceResponse | null;
  defaultOpen?: boolean;
}) {
  if (!evidence || (!evidence.matched_indicator && !evidence.request_summary)) {
    return null;
  }

  return (
    <details open={defaultOpen} className="mt-3 rounded-md border border-black/10 dark:border-white/10">
      <summary className="cursor-pointer select-none px-3 py-2 text-sm font-medium">
        Evidence
      </summary>
      <div className="px-3 pb-3 space-y-2 text-sm">
        {evidence.request_summary ? (
          <p className="text-black/60 dark:text-white/60">{evidence.request_summary}</p>
        ) : null}
        {evidence.matched_indicator ? (
          <pre className="whitespace-pre-wrap break-all rounded bg-black/5 dark:bg-white/10 px-2 py-1.5 text-xs">
            {evidence.matched_indicator}
          </pre>
        ) : null}
        <p className="text-xs text-black/40 dark:text-white/40">
          Captured {new Date(evidence.captured_at).toLocaleString()}
        </p>
      </div>
    </details>
  );
}
