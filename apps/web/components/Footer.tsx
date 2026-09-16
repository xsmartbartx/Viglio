import Link from "next/link";
import { brand } from "../lib/brand";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-black/10 dark:border-white/10 px-6 py-6 text-sm text-black/60 dark:text-white/60">
      <nav className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
        <Link href="/privacy" className="hover:underline">
          Privacy Policy
        </Link>
        <Link href="/terms" className="hover:underline">
          Terms of Service
        </Link>
        <Link href="/cookies" className="hover:underline">
          Cookie Policy
        </Link>
        <Link href="/aup" className="hover:underline">
          Acceptable Use Policy
        </Link>
        <a href={`mailto:${brand.supportEmail}`} className="hover:underline">
          Contact
        </a>
      </nav>
      <p className="mt-4 text-center text-xs text-black/40 dark:text-white/40">
        &copy; {new Date().getFullYear()} {brand.legalName}
      </p>
    </footer>
  );
}
