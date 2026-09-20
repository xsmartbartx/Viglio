"use client";

import { useState } from "react";
import type { ReportFindingResponse } from "../../lib/types";
import { SeverityGroup } from "./SeverityGroup";
import { AcceptedRisksSection } from "./AcceptedRisksSection";

// The one client boundary the report page needs for suppression — kept as
// small and as low in the tree as possible so ScoreHeader/PassedSection/
// SkippedSection stay plain server-rendered markup (never hydrated, so
// their own toLocaleString() calls can't hit a server/client locale
// mismatch). Owns the live-updated `findings` list; suppressing/restoring
// a finding never touches score/grade, so nothing else on the page needs
// to re-render from this state.
export function SuppressibleFindings({
  initialFindings,
  targetId,
  interactive,
  printMode = false,
}: {
  initialFindings: ReportFindingResponse[];
  targetId: string | null;
  interactive: boolean;
  printMode?: boolean;
}) {
  const [findings, setFindings] = useState<ReportFindingResponse[]>(initialFindings);

  function setSuppressed(fingerprint: string, suppressed: boolean) {
    setFindings((current) =>
      current.map((finding) =>
        finding.fingerprint === fingerprint ? { ...finding, suppressed } : finding,
      ),
    );
  }

  return (
    <>
      <SeverityGroup
        findings={findings}
        printMode={printMode}
        targetId={interactive ? targetId : null}
        onSuppressed={(fingerprint) => setSuppressed(fingerprint, true)}
      />
      <AcceptedRisksSection
        targetId={targetId}
        findings={findings}
        interactive={interactive}
        printMode={printMode}
        onRestored={(fingerprint) => setSuppressed(fingerprint, false)}
      />
    </>
  );
}
