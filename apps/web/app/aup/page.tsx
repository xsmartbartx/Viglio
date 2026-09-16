import Link from "next/link";
import { DraftBanner } from "../../components/DraftBanner";
import { Footer } from "../../components/Footer";
import { brand } from "../../lib/brand";

export const metadata = { title: `Acceptable Use Policy — ${brand.name}` };

export default function AcceptableUsePolicyPage() {
  return (
    <>
      <DraftBanner />
      <main className="flex-1 mx-auto w-full max-w-2xl px-6 py-12 space-y-6">
        <div>
          <Link href="/" className="text-sm hover:underline">
            &larr; Back to {brand.name}
          </Link>
          <h1 className="mt-4 text-2xl font-bold">Acceptable Use Policy</h1>
          <p className="mt-1 text-sm text-black/60 dark:text-white/60">
            Last updated: September 2026
          </p>
        </div>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">For people submitting scans</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              Passive-tier scanning is limited to requests an ordinary
              visitor or search-engine crawler would make — you don&apos;t
              need the target owner&apos;s permission to run one.
            </li>
            <li>
              Active-tier scanning (endpoint enumeration and deeper
              probing) requires proof of ownership or control of the
              target, via a DNS record, a well-known file, or a meta tag.
              You may only request active tier for sites you own or are
              explicitly authorized to test.
            </li>
            <li>
              Every scan and its underlying tier decision is written to a
              permanent, append-only audit trail.
            </li>
            <li>
              Scan frequency per target and per account is rate-limited.
              Attempting to circumvent rate limits, authorization checks,
              or the ownership-verification flow is a violation of this
              policy.
            </li>
            <li>
              Do not use {brand.name} to scan infrastructure you know to be
              internal, non-public, or otherwise off-limits (for example,
              cloud metadata endpoints or private network ranges) — the
              service actively blocks known-internal address ranges and
              this is not something to attempt to bypass.
            </li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">For site owners: opting out</h2>
          <p>
            If you own a site and don&apos;t want it scanned by {brand.name} —
            by anyone, at any tier — email{" "}
            <a href={`mailto:${brand.abuseEmail}`} className="underline">
              {brand.abuseEmail}
            </a>{" "}
            from an address associated with the domain, or from an address
            you can otherwise demonstrate control of the domain with, and
            we will add it to our denylist. Today this is a manual,
            support-handled process rather than a self-service form; we aim
            to act on opt-out requests promptly.
          </p>
          <p>
            A denylisted or opted-out target is refused outright — no scan
            runs, and no account or target record is created for the
            request — this takes priority over every other authorization
            check, including a fully verified active-tier proof.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Reporting abuse</h2>
          <p>
            If you believe {brand.name} is being used to scan a target
            abusively, or that the service itself is misbehaving toward
            your infrastructure, email{" "}
            <a href={`mailto:${brand.abuseEmail}`} className="underline">
              {brand.abuseEmail}
            </a>
            . For a security vulnerability in {brand.name} itself, email{" "}
            <a href={`mailto:${brand.securityEmail}`} className="underline">
              {brand.securityEmail}
            </a>{" "}
            instead.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Enforcement</h2>
          <p>
            Violating this policy may result in denylisting the targets
            involved, rate-limiting or suspending the account involved, or
            termination of access to {brand.name}, at our discretion.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Contact</h2>
          <p>
            General questions about this policy can be sent to{" "}
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
