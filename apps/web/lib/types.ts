// TypeScript mirrors of apps/api/src/vigilo_api/schemas.py. Kept in sync by
// hand for now — no codegen this phase.

export type Severity = "critical" | "high" | "medium" | "low" | "info" | "passed";
export type Confidence = "confirmed" | "indicated";
export type Verdict = "passed" | "failed" | "inconclusive" | "not_applicable";
export type Tier = "passive" | "active";

export interface ScanSubmissionResponse {
  scan_job_id: string;
  status: string;
  granted_tier: Tier;
}

export interface ScanStatusResponse {
  scan_job_id: string;
  status: string;
  target_origin: string;
  tier: Tier;
  score: number | null;
  grade: string | null;
  counts_by_severity: Partial<Record<Severity, number>> | null;
  finished_at: string | null;
}

export interface EvidenceResponse {
  matched_indicator: string | null;
  request_summary: string | null;
  redaction_applied: boolean | null;
  captured_at: string;
}

export interface ReportFindingResponse {
  check_id: string;
  category: string;
  title: string;
  severity: Severity;
  confidence: Confidence;
  verdict: Verdict;
  summary: string;
  remediation: string;
  references: string[];
  evidence: EvidenceResponse | null;
  fingerprint: string;
}

export interface ScanReportResponse {
  scan_job_id: string | null;
  is_owner: boolean | null;
  target_origin: string;
  registry_version: string;
  score: number;
  grade: string;
  counts_by_severity: Partial<Record<Severity, number>>;
  generated_at: string;
  findings: ReportFindingResponse[];
}

export interface PdfStatusResponse {
  report_id: string;
  status: "pending" | "complete" | "failed";
  download_url: string | null;
}

export interface ShareLinkCreateResponse {
  share_link_id: string;
  token: string;
  url: string;
  expires_at: string | null;
}

export interface ShareLinkResponse {
  share_link_id: string;
  expires_at: string | null;
  revoked_at: string | null;
  view_count: number;
  created_at: string;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  context?: Record<string, unknown>;
}
