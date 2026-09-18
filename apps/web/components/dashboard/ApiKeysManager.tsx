"use client";

import { useCallback, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api, ApiError } from "../../lib/api";
import type { ApiKeyResponse } from "../../lib/types";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

const ALL_SCOPES = [
  "scan:run",
  "scan:read",
  "project:read",
  "report:read",
  "monitor:read",
  "monitor:write",
];

export function ApiKeysManager({ initialKeys }: { initialKeys: ApiKeyResponse[] }) {
  const { getToken } = useAuth();
  const [keys, setKeys] = useState<ApiKeyResponse[]>(initialKeys);
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>([]);
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const token = await getToken({ template: JWT_TEMPLATE });
    if (!token) return;
    setKeys(await api.listApiKeys(token));
  }, [getToken]);

  function toggleScope(scope: string) {
    setScopes((current) =>
      current.includes(scope) ? current.filter((s) => s !== scope) : [...current, scope],
    );
  }

  async function handleCreate() {
    setError(null);
    setBusy(true);
    try {
      const token = await getToken({ template: JWT_TEMPLATE });
      if (!token) throw new ApiError(401, null);
      const result = await api.createApiKey(name, scopes, token);
      setRevealedKey(result.api_key);
      setCopied(false);
      setName("");
      setScopes([]);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create API key.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke(apiKeyId: string) {
    setError(null);
    try {
      const token = await getToken({ template: JWT_TEMPLATE });
      if (!token) throw new ApiError(401, null);
      await api.revokeApiKey(apiKeyId, token);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't revoke API key.");
    }
  }

  async function handleCopy() {
    if (!revealedKey) return;
    await navigator.clipboard.writeText(revealedKey);
    setCopied(true);
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-black/10 dark:border-white/20 p-4 text-sm space-y-3">
        <p className="font-semibold">New API key</p>
        <label className="block text-xs text-black/60 dark:text-white/60">
          Name
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="CI pipeline"
            className="mt-1 block w-full rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm"
          />
        </label>

        <div className="space-y-1">
          <p className="text-xs text-black/60 dark:text-white/60">Scopes</p>
          <div className="grid grid-cols-2 gap-1 text-xs">
            {ALL_SCOPES.map((scope) => (
              <label key={scope} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={scopes.includes(scope)}
                  onChange={() => toggleScope(scope)}
                />
                {scope}
              </label>
            ))}
          </div>
        </div>

        <button
          type="button"
          onClick={handleCreate}
          disabled={busy || name.trim() === "" || scopes.length === 0}
          className="rounded-md bg-brand-primary px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
        >
          {busy ? "Creating…" : "Create key"}
        </button>

        {revealedKey ? (
          <div className="rounded-md bg-black/5 dark:bg-white/10 px-3 py-2 space-y-2">
            <p className="text-xs text-severity-critical">
              Copy this key now — it won&apos;t be shown again.
            </p>
            <p className="break-all font-mono text-sm">{revealedKey}</p>
            <button
              type="button"
              onClick={handleCopy}
              className="rounded-md border border-black/10 dark:border-white/20 px-3 py-1.5 text-xs font-medium"
            >
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        ) : null}

        {error ? <p className="text-xs text-severity-critical">{error}</p> : null}
      </div>

      {keys.length === 0 ? (
        <p className="text-sm text-black/50 dark:text-white/50">No API keys yet.</p>
      ) : (
        <ul className="space-y-2">
          {keys.map((key) => {
            const isRevoked = Boolean(key.revoked_at);
            return (
              <li
                key={key.api_key_id}
                className="rounded-lg border border-black/10 dark:border-white/20 p-4 text-sm space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className={isRevoked ? "text-black/40 dark:text-white/40" : "font-medium"}>
                    {key.name}
                  </span>
                  {isRevoked ? (
                    <span className="text-xs text-black/40 dark:text-white/40">Revoked</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleRevoke(key.api_key_id)}
                      className="text-xs underline underline-offset-2"
                    >
                      Revoke
                    </button>
                  )}
                </div>
                <p className="text-xs font-mono text-black/50 dark:text-white/50">{key.prefix}…</p>
                <p className="text-xs text-black/50 dark:text-white/50">{key.scopes.join(", ")}</p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
