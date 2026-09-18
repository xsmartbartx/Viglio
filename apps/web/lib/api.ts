// A thin fetch wrapper over apps/api. Works from both Server Components
// (plain server-to-server fetch, no CORS involved) and Client Components
// (the CORS middleware in apps/api/src/vigilo_api/main.py is scoped to
// exactly this: browser calls for PDF export and share-link management).
import type {
  AccountResponse,
  AlertResponse,
  ApiErrorBody,
  ApiKeyCreateResponse,
  ApiKeyResponse,
  BrandingProfileResponse,
  CheckoutResponse,
  MonitorResponse,
  PdfStatusResponse,
  PlanResponse,
  ScanReportResponse,
  ScanStatusResponse,
  ScanSubmissionResponse,
  ScoreHistoryEntry,
  ShareLinkCreateResponse,
  ShareLinkResponse,
  TargetResponse,
  VerificationCheckResponse,
  VerificationInitiateResponse,
  VerificationMethod,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | null;

  constructor(status: number, body: ApiErrorBody | null) {
    super(body?.message ?? `API request failed with status ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit & { token?: string | null },
): Promise<T> {
  const { token, ...rest } = init ?? {};
  const headers = new Headers(rest.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (rest.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // no JSON body on this error response
    }
    throw new ApiError(response.status, body);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  submitScan: (body: { target_url: string; email: string }) =>
    request<ScanSubmissionResponse>("/v1/scans", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getScanStatus: (scanJobId: string) => request<ScanStatusResponse>(`/v1/scans/${scanJobId}`),

  getScanReport: (scanJobId: string, token?: string | null) =>
    request<ScanReportResponse>(`/v1/scans/${scanJobId}/report`, { token }),

  getShareReport: (token: string) => request<ScanReportResponse>(`/v1/share/${token}`),

  requestReportPdf: (scanJobId: string) =>
    request<PdfStatusResponse>(`/v1/scans/${scanJobId}/report/pdf`, { method: "POST" }),

  getReportPdfStatus: (scanJobId: string) =>
    request<PdfStatusResponse>(`/v1/scans/${scanJobId}/report/pdf`),

  createShareLink: (scanJobId: string, token: string, expiresInDays?: number | null) =>
    request<ShareLinkCreateResponse>(`/v1/scans/${scanJobId}/share-links`, {
      method: "POST",
      token,
      body: JSON.stringify({ expires_in_days: expiresInDays ?? null }),
    }),

  listShareLinks: (scanJobId: string, token: string) =>
    request<ShareLinkResponse[]>(`/v1/scans/${scanJobId}/share-links`, { token }),

  revokeShareLink: (shareLinkId: string, token: string) =>
    request<{ share_link_id: string; revoked_at: string }>(
      `/v1/share-links/${shareLinkId}/revoke`,
      { method: "POST", token },
    ),

  getMe: (token: string) => request<AccountResponse>("/v1/me", { token }),

  getTarget: (targetId: string, token: string) =>
    request<TargetResponse>(`/v1/targets/${targetId}`, { token }),

  getTargetMonitor: (targetId: string, token: string) =>
    request<MonitorResponse>(`/v1/targets/${targetId}/monitors`, { token }),

  createTargetMonitor: (
    targetId: string,
    token: string,
    body: { cadence_hours: number; quiet_start_utc?: number | null; quiet_end_utc?: number | null },
  ) =>
    request<MonitorResponse>(`/v1/targets/${targetId}/monitors`, {
      method: "POST",
      token,
      body: JSON.stringify(body),
    }),

  disableMonitor: (monitorId: string, token: string) =>
    request<MonitorResponse>(`/v1/monitors/${monitorId}/disable`, { method: "POST", token }),

  getTargetScoreHistory: (targetId: string, token: string) =>
    request<ScoreHistoryEntry[]>(`/v1/targets/${targetId}/scores`, { token }),

  getTargetAlerts: (targetId: string, token: string) =>
    request<AlertResponse[]>(`/v1/targets/${targetId}/alerts`, { token }),

  listTargets: (token: string) => request<TargetResponse[]>("/v1/targets", { token }),

  createTarget: (origin: string, token: string) =>
    request<TargetResponse>("/v1/targets", {
      method: "POST",
      token,
      body: JSON.stringify({ origin }),
    }),

  initiateVerification: (targetId: string, method: VerificationMethod, token: string) =>
    request<VerificationInitiateResponse>(`/v1/targets/${targetId}/verification`, {
      method: "POST",
      token,
      body: JSON.stringify({ method }),
    }),

  checkVerification: (targetId: string, proofId: string, token: string) =>
    request<VerificationCheckResponse>(
      `/v1/targets/${targetId}/verification/${proofId}/check`,
      { method: "POST", token },
    ),

  listPlans: () => request<PlanResponse[]>("/v1/plans"),

  createCheckout: (planId: string, token: string) =>
    request<CheckoutResponse>("/v1/billing/checkout", {
      method: "POST",
      token,
      body: JSON.stringify({ plan_id: planId }),
    }),

  createApiKey: (name: string, scopes: string[], token: string) =>
    request<ApiKeyCreateResponse>("/v1/me/api-keys", {
      method: "POST",
      token,
      body: JSON.stringify({ name, scopes }),
    }),

  listApiKeys: (token: string) => request<ApiKeyResponse[]>("/v1/me/api-keys", { token }),

  revokeApiKey: (apiKeyId: string, token: string) =>
    request<ApiKeyResponse>(`/v1/me/api-keys/${apiKeyId}/revoke`, { method: "POST", token }),

  getBrandingProfile: (token: string) =>
    request<BrandingProfileResponse>("/v1/me/branding-profile", { token }),

  updateBrandingProfile: (
    body: {
      logo_url?: string;
      primary_color?: string;
      footer_text?: string;
      custom_domain?: string;
    },
    token: string,
  ) =>
    request<BrandingProfileResponse>("/v1/me/branding-profile", {
      method: "PUT",
      token,
      body: JSON.stringify(body),
    }),
};

export function apiBaseUrl(): string {
  return API_BASE_URL;
}
