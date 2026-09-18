"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api, ApiError } from "../../lib/api";
import type { TargetResponse, VerificationInitiateResponse, VerificationMethod } from "../../lib/types";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

// "email" is deliberately excluded — the backend's own instructions string
// for it is "Email verification is not yet available."
const METHODS: { value: VerificationMethod; label: string }[] = [
  { value: "dns_txt", label: "DNS TXT record" },
  { value: "wellknown_file", label: "Well-known file" },
  { value: "meta_tag", label: "Meta tag" },
];

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function VerificationPanel({
  targetId,
  onVerified,
}: {
  targetId: string;
  onVerified: (target: TargetResponse) => void;
}) {
  const { getToken } = useAuth();
  const [method, setMethod] = useState<VerificationMethod>("dns_txt");
  const [proof, setProof] = useState<VerificationInitiateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGetInstructions() {
    setError(null);
    setBusy(true);
    try {
      const token = await getToken({ template: JWT_TEMPLATE });
      if (!token) throw new ApiError(401, null);
      const result = await api.initiateVerification(targetId, method, token);
      setProof(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start verification.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCheckNow() {
    if (!proof) return;
    setError(null);
    setBusy(true);
    try {
      const token = await getToken({ template: JWT_TEMPLATE });
      if (!token) throw new ApiError(401, null);
      await api.checkVerification(targetId, proof.proof_id, token);

      for (let attempt = 0; attempt < 5; attempt++) {
        await wait(2000);
        const target = await api.getTarget(targetId, token);
        if (target.verification_status === "active") {
          onVerified(target);
          return;
        }
      }
      setError("Still checking — this can take a bit longer. Try “Check now” again shortly.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't check verification.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2 rounded-md border border-black/10 dark:border-white/20 p-3 text-xs space-y-2">
      {!proof ? (
        <>
          <label className="block text-black/60 dark:text-white/60">
            Verification method
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value as VerificationMethod)}
              className="mt-1 block w-full rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm"
            >
              {METHODS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={handleGetInstructions}
            disabled={busy}
            className="rounded-md border border-black/10 dark:border-white/20 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
          >
            {busy ? "Working…" : "Get verification instructions"}
          </button>
        </>
      ) : (
        <>
          <p className="break-words rounded bg-black/5 dark:bg-white/10 px-3 py-2 font-mono">
            {proof.instructions}
          </p>
          <button
            type="button"
            onClick={handleCheckNow}
            disabled={busy}
            className="rounded-md bg-brand-primary px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
          >
            {busy ? "Checking…" : "Check now"}
          </button>
        </>
      )}

      {error ? <p className="text-severity-critical">{error}</p> : null}
    </div>
  );
}
