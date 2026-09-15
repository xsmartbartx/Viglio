"use client";

import { useState } from "react";
import { api, apiBaseUrl, ApiError } from "../../lib/api";
import type { PdfStatusResponse } from "../../lib/types";

type Status = "idle" | "pending" | "complete" | "failed";

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function ExportPdfButton({ scanJobId }: { scanJobId: string }) {
  const [status, setStatus] = useState<Status>("idle");
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setError(null);
    setStatus("pending");
    try {
      let result: PdfStatusResponse = await api.requestReportPdf(scanJobId);
      while (result.status === "pending") {
        await wait(2000);
        result = await api.getReportPdfStatus(scanJobId);
      }
      if (result.status === "complete" && result.download_url) {
        setDownloadUrl(`${apiBaseUrl()}${result.download_url}`);
        setStatus("complete");
      } else {
        setStatus("failed");
        setError("PDF export failed. Try again.");
      }
    } catch (err) {
      setStatus("failed");
      setError(err instanceof ApiError ? err.message : "PDF export failed. Try again.");
    }
  }

  if (status === "complete" && downloadUrl) {
    return (
      <a
        href={downloadUrl}
        target="_blank"
        rel="noreferrer noopener"
        className="rounded-md border border-black/10 dark:border-white/20 px-3 py-1.5 text-sm font-medium"
      >
        Download PDF
      </a>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={handleClick}
        disabled={status === "pending"}
        className="rounded-md border border-black/10 dark:border-white/20 px-3 py-1.5 text-sm font-medium disabled:opacity-60"
      >
        {status === "pending" ? "Preparing PDF…" : "Export PDF"}
      </button>
      {error ? <p className="mt-1 text-xs text-severity-critical">{error}</p> : null}
    </div>
  );
}
