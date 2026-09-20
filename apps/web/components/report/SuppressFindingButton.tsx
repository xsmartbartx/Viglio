"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api, ApiError } from "../../lib/api";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

export function SuppressFindingButton({
  targetId,
  fingerprint,
  checkId,
  onSuppressed,
}: {
  targetId: string;
  fingerprint: string;
  checkId: string;
  onSuppressed: () => void;
}) {
  const { getToken } = useAuth();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    setError(null);
    setBusy(true);
    try {
      const token = await getToken({ template: JWT_TEMPLATE });
      if (!token) throw new ApiError(401, null);
      await api.suppressFinding(targetId, { fingerprint, check_id: checkId, reason }, token);
      setOpen(false);
      setReason("");
      onSuppressed();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't accept this risk.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs text-black/50 dark:text-white/50 underline underline-offset-2"
      >
        Accept risk
      </button>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Why is this accepted? (e.g. compensating control in place)"
          className="min-w-0 flex-1 rounded border border-black/10 dark:border-white/20 bg-transparent px-2 py-1 text-xs"
        />
        <button
          type="button"
          onClick={handleConfirm}
          disabled={busy || reason.trim().length === 0}
          className="shrink-0 rounded-md border border-black/10 dark:border-white/20 px-2 py-1 text-xs font-medium disabled:opacity-60"
        >
          {busy ? "Saving…" : "Confirm"}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          disabled={busy}
          className="shrink-0 text-xs text-black/40 dark:text-white/40"
        >
          Cancel
        </button>
      </div>
      {error ? <p className="mt-1 text-xs text-severity-critical">{error}</p> : null}
    </div>
  );
}
