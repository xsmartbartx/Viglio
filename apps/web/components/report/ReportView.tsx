"use client";

import { useState } from "react";
import Link from "next/link";
import type { ReportFindingResponse, ScanReportResponse, ShareLinkResponse } from "../../lib/types";
import { ScoreHeader } from "./ScoreHeader";
import { SeverityGroup } from "./SeverityGroup";
import { PassedSection } from "./PassedSection";
import { SkippedSection } from "./SkippedSection";
import { AcceptedRisksSection } from "./AcceptedRisksSection";
import { ExportPdfButton } from "./ExportPdfButton";
import { ShareLinkManager } from "./ShareLinkManager";

export function ReportView({
  report,
  printMode = false,
  initialShareLinks = [],
}: {
  report: ScanReportResponse;
  printMode?: boolean;
  initialShareLinks?: ShareLinkResponse[];
}) {
  // Suppression state lives here, not in `report` — accepting/restoring a
  // risk updates this list in place from the endpoint's own response rather
  // than re-fetching the whole report (score/grade never change from this,
  // see packages/reporting's build_report(), so there's nothing else to
  // re-sync).
  const [findings, setFindings] = useState<ReportFindingResponse[]>(report.findings);
  const showOwnerControls = Boolean(report.is_owner) && !printMode && Boolean(report.scan_job_id);

  function setSuppressed(fingerprint: string, suppressed: boolean) {
    setFindings((current) =>
      current.map((finding) =>
        finding.fingerprint === fingerprint ? { ...finding, suppressed } : finding,
      ),
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-10">
      <ScoreHeader report={report} />

      {showOwnerControls ? (
        <div className="mb-6 flex items-center gap-3">
          <ExportPdfButton scanJobId={report.scan_job_id as string} />
          {report.target_id ? (
            <Link
              href={`/targets/${report.target_id}/monitoring`}
              className="rounded-md border border-black/10 dark:border-white/20 px-3 py-1.5 text-sm font-medium"
            >
              Manage monitoring
            </Link>
          ) : null}
        </div>
      ) : null}

      <SeverityGroup
        findings={findings}
        printMode={printMode}
        targetId={showOwnerControls ? report.target_id : null}
        onSuppressed={(fingerprint) => setSuppressed(fingerprint, true)}
      />
      <PassedSection findings={findings} printMode={printMode} />
      <SkippedSection findings={findings} printMode={printMode} />
      <AcceptedRisksSection
        targetId={report.target_id}
        findings={findings}
        interactive={showOwnerControls}
        printMode={printMode}
        onRestored={(fingerprint) => setSuppressed(fingerprint, false)}
      />

      {showOwnerControls ? (
        <ShareLinkManager scanJobId={report.scan_job_id as string} initialLinks={initialShareLinks} />
      ) : null}
    </div>
  );
}
