import Link from "next/link";
import { DraftBanner } from "../../components/DraftBanner";
import { Footer } from "../../components/Footer";
import { brand } from "../../lib/brand";

export const metadata = { title: `Cookie Policy — ${brand.name}` };

export default function CookiePolicyPage() {
  return (
    <>
      <DraftBanner />
      <main className="flex-1 mx-auto w-full max-w-2xl px-6 py-12 space-y-6">
        <div>
          <Link href="/" className="text-sm hover:underline">
            &larr; Back to {brand.name}
          </Link>
          <h1 className="mt-4 text-2xl font-bold">Cookie Policy</h1>
          <p className="mt-1 text-sm text-black/60 dark:text-white/60">
            Last updated: September 2026
          </p>
        </div>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">What we use cookies for</h2>
          <p>
            {brand.name} uses a small number of cookies to run the service.
            We do not use cookies for advertising, and we do not sell any
            data collected via cookies.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Strictly necessary cookies</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              <strong>Session/authentication cookies</strong> — set by our
              authentication provider (Clerk) to keep you signed in between
              page loads. Without these, you would need to sign in on every
              page.
            </li>
          </ul>
          <p>
            These cookies are required for the service to function and are
            not subject to opt-out, consistent with EU ePrivacy exemptions
            for strictly necessary cookies.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">What we don&apos;t use</h2>
          <p>
            We do not currently set any analytics, advertising, or
            third-party tracking cookies. If that changes, this page will
            be updated and, where required, we will ask for your consent
            before setting non-essential cookies.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Managing cookies</h2>
          <p>
            Most browsers let you block or delete cookies through their
            settings. Because {brand.name} currently only sets strictly
            necessary authentication cookies, blocking them will prevent
            you from staying signed in.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Related policies</h2>
          <p>
            See our{" "}
            <Link href="/privacy" className="underline">
              Privacy Policy
            </Link>{" "}
            for how we handle personal data more broadly.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Contact</h2>
          <p>
            Questions about this policy can be sent to{" "}
            <a href={`mailto:${brand.supportEmail}`} className="underline">
              {brand.supportEmail}
            </a>
            .
          </p>
        </section>
      </main>
      <Footer />
    </>
  );
}
