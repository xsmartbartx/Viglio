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

export type EstimatedEffort = "trivial" | "small" | "medium" | "large";

export interface RemediationResponse {
  source: "template" | "llm";
  explanation: string;
  impact: string;
  remediation_steps: string[];
  agent_prompt: string;
  estimated_effort: EstimatedEffort | null;
}

export interface ReportFindingResponse {
  check_id: string;
  category: string;
  title: string;
  severity: Severity;
  confidence: Confidence;
  verdict: Verdict;
  summary: string;
  remediation: RemediationResponse;
  references: string[];
  evidence: EvidenceResponse | null;
  fingerprint: string;
}

export interface BrandingProfileResponse {
  logo_url: string | null;
  primary_color: string | null;
  footer_text: string | null;
  custom_domain: string | null;
}

export interface ScanReportResponse {
  scan_job_id: string | null;
  target_id: string | null;
  is_owner: boolean | null;
  target_origin: string;
  registry_version: string;
  score: number;
  grade: string;
  counts_by_severity: Partial<Record<Severity, number>>;
  generated_at: string;
  findings: ReportFindingResponse[];
  branding: BrandingProfileResponse | null;
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

export interface EntitlementsResponse {
  plan_id: string;
  targets_limit: number | null;
  scans_per_month_limit: number | null;
  active_tier_allowed: boolean;
  share_links_allowed: boolean;
  monitoring_frequency: string | null;
  monitors_limit: number | null;
  api_keys_limit: number | null;
  api_rate_limit_per_minute: number | null;
  white_label_allowed: boolean;
  repo_connectors_limit: number | null;
}

export interface AccountResponse {
  account_id: string;
  email: string;
  status: string;
  created_at: string;
  entitlements: EntitlementsResponse;
}

export interface PlanResponse {
  plan_id: string;
  targets_limit: number | null;
  scans_per_month_limit: number | null;
  active_tier_allowed: boolean;
  share_links_allowed: boolean;
  monitoring_frequency: string | null;
  monitors_limit: number | null;
  api_keys_limit: number | null;
  api_rate_limit_per_minute: number | null;
  white_label_allowed: boolean;
  repo_connectors_limit: number | null;
}

export interface CheckoutResponse {
  checkout_url: string;
}

export type VerificationMethod = "dns_txt" | "wellknown_file" | "meta_tag" | "email";

export interface VerificationInitiateResponse {
  proof_id: string;
  method: VerificationMethod;
  nonce: string;
  instructions: string;
}

export interface VerificationCheckResponse {
  proof_id: string;
  status: string;
}

export interface ApiKeyResponse {
  api_key_id: string;
  name: string;
  prefix: string;
  scopes: string[];
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface ApiKeyCreateResponse {
  api_key_id: string;
  name: string;
  prefix: string;
  scopes: string[];
  api_key: string; // plaintext — present only in this response, once
}

export interface TargetResponse {
  target_id: string;
  origin: string;
  verification_status: Tier;
  verified_at: string | null;
  verification_method: string | null;
}

export interface MonitorResponse {
  monitor_id: string;
  target_id: string;
  cadence_hours: number;
  enabled: boolean;
  next_run_at: string;
  quiet_start_utc: number | null;
  quiet_end_utc: number | null;
}

export interface ScoreHistoryEntry {
  scan_id: string;
  score: number;
  grade: string;
  registry_version: string;
  created_at: string;
}

export type AlertType =
  | "new_critical"
  | "new_high"
  | "regressed"
  | "cert_expiry"
  | "score_drop"
  | "scan_failed";

export interface AlertResponse {
  alert_id: string;
  type: AlertType;
  severity: Severity | null;
  fingerprint: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  context?: Record<string, unknown>;
}
