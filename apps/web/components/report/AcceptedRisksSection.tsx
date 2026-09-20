"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api, ApiError } from "../../lib/api";
import type { ReportFindingResponse } from "../../lib/types";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

// Findings the owner has explicitly accepted (packages/project's
// Suppression) — grouped apart from HIGH/MEDIUM/LOW rather than hidden.
// They still count toward the score (docs/security.md), which is why this
// section says so rather than letting an "accepted" finding read as
// resolved.
export function AcceptedRisksSection({
  targetId,
  findings,
  interactive,
  printMode = false,
  onRestored,
}: {
  targetId: string | null;
  findings: ReportFindingResponse[];
  interactive: boolean;
  printMode?: boolean;
  onRestored: (fingerprint: string) => void;
}) {
  const { getToken } = useAuth();
  const accepted = findings.filter((finding) => finding.suppressed);
  const [suppressionIds, setSuppressionIds] = useState<Record<string, string>>({});
  const [busyFingerprint, setBusyFingerprint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!interactive || !targetId || accepted.length === 0) return;
    let cancelled = false;

    (async () => {
      try {
        const token = await getToken({ template: JWT_TEMPLATE });
        if (!token) return;
        const list = await api.listSuppressions(targetId, token);
        if (cancelled) return;
        setSuppressionIds(
          Object.fromEntries(list.map((item) => [item.fingerprint, item.suppression_id])),
        );
      } catch {
        // Best-effort lookup only — "Restore" simply stays disabled below.
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interactive, targetId, accepted.length]);

  if (accepted.length === 0) return null;

  async function handleRestore(fingerprint: string) {
    const suppressionId = suppressionIds[fingerprint];
    if (!targetId || !suppressionId) return;
    setError(null);
    setBusyFingerprint(fingerprint);
    try {
      const token = await getToken({ template: JWT_TEMPLATE });
      if (!token) throw new ApiError(401, null);
      await api.revokeSuppression(targetId, suppressionId, token);
      onRestored(fingerprint);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't restore this finding.");
    } finally {
      setBusyFingerprint(null);
    }
  }

  return (
    <details
      open={printMode}
      className="mt-8 border-t border-black/10 dark:border-white/10 pt-6 text-sm"
    >
      <summary className="cursor-pointer select-none font-semibold uppercase tracking-wide text-black/50 dark:text-white/50">
        Accepted risks ({accepted.length})
      </summary>
      <p className="mt-1 text-xs text-black/50 dark:text-white/50 max-w-prose">
        Marked as a known, accepted risk by the target owner. Still counted in the score above and
        excluded from SARIF export and monitoring alerts.
      </p>
      {error ? <p className="mt-2 text-xs text-severity-critical">{error}</p> : null}
      <ul className="mt-2 space-y-2">
        {accepted.map((finding) => (
          <li key={finding.fingerprint} className="flex items-start justify-between gap-3">
            <div>
              <span className="font-medium">{finding.title}</span>
              <span className="ml-2 text-xs text-black/40 dark:text-white/40">
                {finding.check_id}
              </span>
            </div>
            {interactive && !printMode ? (
              <button
                type="button"
                onClick={() => handleRestore(finding.fingerprint)}
                disabled={busyFingerprint === finding.fingerprint || !suppressionIds[finding.fingerprint]}
                className="shrink-0 text-xs underline underline-offset-2 disabled:opacity-60"
              >
                Restore
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </details>
  );
}
