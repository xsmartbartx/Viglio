import Link from "next/link";
import type { ScanReportResponse, ShareLinkResponse } from "../../lib/types";
import { ScoreHeader } from "./ScoreHeader";
import { SuppressibleFindings } from "./SuppressibleFindings";
import { PassedSection } from "./PassedSection";
import { SkippedSection } from "./SkippedSection";
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
  const showOwnerControls = Boolean(report.is_owner) && !printMode && Boolean(report.scan_job_id);

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

      <SuppressibleFindings
        initialFindings={report.findings}
        targetId={report.target_id}
        interactive={showOwnerControls}
        printMode={printMode}
      />
      <PassedSection findings={report.findings} printMode={printMode} />
      <SkippedSection findings={report.findings} printMode={printMode} />

      {showOwnerControls ? (
        <ShareLinkManager scanJobId={report.scan_job_id as string} initialLinks={initialShareLinks} />
      ) : null}
    </div>
  );
}
