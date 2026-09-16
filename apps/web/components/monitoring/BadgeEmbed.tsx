import { apiBaseUrl } from "../../lib/api";

export function BadgeEmbed({ targetId }: { targetId: string }) {
  const badgeUrl = `${apiBaseUrl()}/badge/${targetId}.svg`;
  const snippet = `<img src="${badgeUrl}" alt="Vigilo score badge" />`;

  return (
    <div className="rounded-lg border border-black/10 dark:border-white/10 p-4">
      <p className="text-sm font-semibold mb-2">Embeddable badge</p>
      {/* eslint-disable-next-line @next/next/no-img-element -- external, cross-origin SVG served by apps/api, not a Next-optimizable local asset */}
      <img src={badgeUrl} alt="Vigilo score badge" className="mb-2" />
      <p className="text-xs text-black/60 dark:text-white/60 mb-1">
        Updates automatically after each scan. Copy this into your README or site:
      </p>
      <pre className="overflow-x-auto rounded bg-black/5 dark:bg-white/10 px-3 py-2 text-xs">
        {snippet}
      </pre>
    </div>
  );
}
