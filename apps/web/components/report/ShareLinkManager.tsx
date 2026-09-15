"use client";

import { useCallback, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api, ApiError } from "../../lib/api";
import type { ShareLinkResponse } from "../../lib/types";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

export function ShareLinkManager({
  scanJobId,
  initialLinks,
}: {
  scanJobId: string;
  initialLinks: ShareLinkResponse[];
}) {
  const { getToken } = useAuth();
  const [links, setLinks] = useState<ShareLinkResponse[]>(initialLinks);
  const [creating, setCreating] = useState(false);
  const [newLinkUrl, setNewLinkUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const token = await getToken({ template: JWT_TEMPLATE });
    if (!token) return;
    setLinks(await api.listShareLinks(scanJobId, token));
  }, [getToken, scanJobId]);

  async function handleCreate() {
    setError(null);
    setCreating(true);
    try {
      const token = await getToken({ template: JWT_TEMPLATE });
      if (!token) throw new ApiError(401, null);
      const result = await api.createShareLink(scanJobId, token);
      setNewLinkUrl(result.url);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create share link.");
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(shareLinkId: string) {
    setError(null);
    try {
      const token = await getToken({ template: JWT_TEMPLATE });
      if (!token) throw new ApiError(401, null);
      await api.revokeShareLink(shareLinkId, token);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't revoke share link.");
    }
  }

  return (
    <div className="mt-8 border-t border-black/10 dark:border-white/10 pt-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-black/50 dark:text-white/50">
          Share this report
        </h2>
        <button
          type="button"
          onClick={handleCreate}
          disabled={creating}
          className="rounded-md border border-black/10 dark:border-white/20 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
        >
          {creating ? "Creating…" : "New share link"}
        </button>
      </div>

      {newLinkUrl ? (
        <p className="mt-2 break-all rounded bg-black/5 dark:bg-white/10 px-3 py-2 text-sm">{newLinkUrl}</p>
      ) : null}

      {error ? <p className="mt-2 text-xs text-severity-critical">{error}</p> : null}

      {links.length === 0 ? (
        <p className="mt-2 text-sm text-black/50 dark:text-white/50">No share links yet.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {links.map((link) => {
            const isRevoked = Boolean(link.revoked_at);
            return (
              <li key={link.share_link_id} className="flex items-center justify-between text-sm">
                <span className={isRevoked ? "text-black/40 dark:text-white/40" : ""}>
                  {isRevoked ? "Revoked" : "Active"} · {link.view_count} view
                  {link.view_count === 1 ? "" : "s"}
                  {link.expires_at ? ` · expires ${new Date(link.expires_at).toLocaleDateString()}` : ""}
                </span>
                {!isRevoked ? (
                  <button
                    type="button"
                    onClick={() => handleRevoke(link.share_link_id)}
                    className="text-xs underline underline-offset-2"
                  >
                    Revoke
                  </button>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
