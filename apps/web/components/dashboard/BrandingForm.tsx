"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api, ApiError } from "../../lib/api";
import type { BrandingProfileResponse } from "../../lib/types";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

export function BrandingForm({ initialProfile }: { initialProfile: BrandingProfileResponse }) {
  const { getToken } = useAuth();
  const [logoUrl, setLogoUrl] = useState(initialProfile.logo_url ?? "");
  const [primaryColor, setPrimaryColor] = useState(initialProfile.primary_color ?? "");
  const [footerText, setFooterText] = useState(initialProfile.footer_text ?? "");
  const [customDomain, setCustomDomain] = useState(initialProfile.custom_domain ?? "");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setError(null);
    setSaved(false);
    setBusy(true);
    try {
      const token = await getToken({ template: JWT_TEMPLATE });
      if (!token) throw new ApiError(401, null);

      // The endpoint's PUT is a partial update — only fields the caller
      // actually sends are written, so only include ones the user changed
      // from what was loaded (an unedited field must never overwrite
      // itself with an empty string).
      const body: {
        logo_url?: string;
        primary_color?: string;
        footer_text?: string;
        custom_domain?: string;
      } = {};
      if (logoUrl !== (initialProfile.logo_url ?? "")) body.logo_url = logoUrl;
      if (primaryColor !== (initialProfile.primary_color ?? "")) body.primary_color = primaryColor;
      if (footerText !== (initialProfile.footer_text ?? "")) body.footer_text = footerText;
      if (customDomain !== (initialProfile.custom_domain ?? "")) body.custom_domain = customDomain;

      await api.updateBrandingProfile(body, token);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save branding.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-black/10 dark:border-white/20 p-4 text-sm space-y-3">
      <label className="block text-xs text-black/60 dark:text-white/60">
        Logo URL
        <input
          type="text"
          value={logoUrl}
          onChange={(e) => setLogoUrl(e.target.value)}
          placeholder="https://example.com/logo.png"
          className="mt-1 block w-full rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm"
        />
      </label>
      <label className="block text-xs text-black/60 dark:text-white/60">
        Primary color
        <input
          type="text"
          value={primaryColor}
          onChange={(e) => setPrimaryColor(e.target.value)}
          placeholder="#112233"
          className="mt-1 block w-full rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm"
        />
      </label>
      <label className="block text-xs text-black/60 dark:text-white/60">
        Footer text
        <input
          type="text"
          value={footerText}
          onChange={(e) => setFooterText(e.target.value)}
          placeholder="Provided by Acme Security"
          className="mt-1 block w-full rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm"
        />
      </label>
      <label className="block text-xs text-black/60 dark:text-white/60">
        Custom domain
        <input
          type="text"
          value={customDomain}
          onChange={(e) => setCustomDomain(e.target.value)}
          placeholder="reports.example.com"
          className="mt-1 block w-full rounded-md border border-black/10 dark:border-white/20 bg-transparent px-2 py-1.5 text-sm"
        />
      </label>

      <button
        type="button"
        onClick={handleSave}
        disabled={busy}
        className="rounded-md bg-brand-primary px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
      >
        {busy ? "Saving…" : "Save"}
      </button>

      {saved ? <p className="text-xs text-severity-pass">Saved.</p> : null}
      {error ? <p className="text-xs text-severity-critical">{error}</p> : null}
    </div>
  );
}
