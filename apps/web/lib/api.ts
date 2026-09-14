// A thin fetch wrapper over apps/api. Works from both Server Components
// (plain server-to-server fetch, no CORS involved) and Client Components
// (the CORS middleware in apps/api/src/vigilo_api/main.py is scoped to
// exactly this: browser calls for PDF export and share-link management).
import type {
  ApiErrorBody,
  PdfStatusResponse,
  ScanReportResponse,
  ScanStatusResponse,
  ScanSubmissionResponse,
  ShareLinkCreateResponse,
  ShareLinkResponse,
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
};

export function apiBaseUrl(): string {
  return API_BASE_URL;
}
