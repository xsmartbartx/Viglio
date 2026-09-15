import type { ScanReportResponse, ShareLinkResponse } from "../../lib/types";
import { ScoreHeader } from "./ScoreHeader";
import { SeverityGroup } from "./SeverityGroup";
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
        <div className="mb-6">
          <ExportPdfButton scanJobId={report.scan_job_id as string} />
        </div>
      ) : null}

      <SeverityGroup findings={report.findings} printMode={printMode} />
      <PassedSection findings={report.findings} printMode={printMode} />
      <SkippedSection findings={report.findings} printMode={printMode} />

      {showOwnerControls ? (
        <ShareLinkManager scanJobId={report.scan_job_id as string} initialLinks={initialShareLinks} />
      ) : null}
    </div>
  );
}
