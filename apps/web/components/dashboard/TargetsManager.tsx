"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api, ApiError } from "../../lib/api";
import type { TargetResponse } from "../../lib/types";
import { TargetRow } from "./TargetRow";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

export function TargetsManager({ initialTargets }: { initialTargets: TargetResponse[] }) {
  const { getToken } = useAuth();
  const [targets, setTargets] = useState<TargetResponse[]>(initialTargets);
  const [origin, setOrigin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAdd() {
    setError(null);
    setBusy(true);
    try {
      const token = await getToken({ template: JWT_TEMPLATE });
      if (!token) throw new ApiError(401, null);
      const target = await api.createTarget(origin, token);
      setTargets((current) => [...current, target]);
      setOrigin("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't add target.");
    } finally {
      setBusy(false);
    }
  }

  function handleVerified(updated: TargetResponse) {
    setTargets((current) =>
      current.map((target) => (target.target_id === updated.target_id ? updated : target)),
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          type="text"
          value={origin}
          onChange={(e) => setOrigin(e.target.value)}
          placeholder="https://example.com"
          className="flex-1 rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm"
        />
        <button
          type="button"
          onClick={handleAdd}
          disabled={busy || origin.trim() === ""}
          className="rounded-md bg-brand-primary px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
        >
          {busy ? "Adding…" : "Add target"}
        </button>
      </div>

      {error ? <p className="text-xs text-severity-critical">{error}</p> : null}

      {targets.length === 0 ? (
        <p className="text-sm text-black/50 dark:text-white/50">No targets yet.</p>
      ) : (
        <ul className="space-y-2">
          {targets.map((target) => (
            <TargetRow key={target.target_id} target={target} onVerified={handleVerified} />
          ))}
        </ul>
      )}
    </div>
  );
}
