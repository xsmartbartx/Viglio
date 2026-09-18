import Link from "next/link";

const LINKS = [
  { href: "/dashboard", label: "Overview" },
  { href: "/dashboard/targets", label: "Targets" },
  { href: "/dashboard/billing", label: "Billing" },
  { href: "/dashboard/api-keys", label: "API keys" },
  { href: "/dashboard/branding", label: "Branding" },
];

export function DashboardNav() {
  return (
    <>
      {LINKS.map((link) => (
        <Link key={link.href} href={link.href} className="text-black/60 dark:text-white/60 hover:underline">
          {link.label}
        </Link>
      ))}
    </>
  );
}
