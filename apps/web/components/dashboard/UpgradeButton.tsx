"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api, ApiError } from "../../lib/api";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

export function UpgradeButton({ planId }: { planId: string }) {
  const { getToken } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setError(null);
    setBusy(true);
    try {
      const token = await getToken({ template: JWT_TEMPLATE });
      if (!token) throw new ApiError(401, null);
      const { checkout_url } = await api.createCheckout(planId, token);
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start checkout.");
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={handleClick}
        disabled={busy}
        className="rounded-md bg-brand-primary px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
      >
        {busy ? "Starting…" : "Upgrade"}
      </button>
      {error ? <p className="mt-1 text-xs text-severity-critical">{error}</p> : null}
    </div>
  );
}
