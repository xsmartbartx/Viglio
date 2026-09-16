import Link from "next/link";
import { DraftBanner } from "../../components/DraftBanner";
import { Footer } from "../../components/Footer";
import { brand } from "../../lib/brand";

export const metadata = { title: `Privacy Policy — ${brand.name}` };

export default function PrivacyPolicyPage() {
  return (
    <>
      <DraftBanner />
      <main className="flex-1 mx-auto w-full max-w-2xl px-6 py-12 space-y-6">
        <div>
          <Link href="/" className="text-sm hover:underline">
            &larr; Back to {brand.name}
          </Link>
          <h1 className="mt-4 text-2xl font-bold">Privacy Policy</h1>
          <p className="mt-1 text-sm text-black/60 dark:text-white/60">
            Last updated: September 2026
          </p>
        </div>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">What {brand.name} does</h2>
          <p>
            {brand.name} ({brand.legalName}) is a security and compliance
            scanner. You submit a URL; we run a series of passive and, where
            authorized, active checks against it and produce a report. This
            policy covers the personal data we collect from you as a user of
            the service, and separately, how we handle data belonging to the
            sites we scan.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Data we collect from you</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              <strong>Email address</strong> — required to submit a scan or
              create an account, used to identify your account and deliver
              scan results.
            </li>
            <li>
              <strong>Account and authentication data</strong> — if you sign
              in, our authentication provider (Clerk) manages your
              credentials; we store the resulting account identifier, not
              your password.
            </li>
            <li>
              <strong>Submitted target URLs</strong> — the sites you ask us
              to scan, and the reports we generate from those scans.
            </li>
            <li>
              <strong>Billing information</strong> — if you subscribe to a
              paid plan, payment details are collected and processed
              directly by our merchant-of-record payment provider; we
              receive only your subscription status and plan, never your
              card details.
            </li>
            <li>
              <strong>Operational logs</strong> — standard request logs and
              an audit trail of authorization decisions (what was scanned,
              at what tier, and why), kept for security and debugging.
            </li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">
            How we handle data about scanned sites
          </h2>
          <p>
            A scan captures evidence — response headers, page content
            excerpts, and similar technical artifacts — needed to justify
            each finding in your report. Before this evidence is stored, any
            value that looks like a secret (an API key, token, or
            credential) is redacted; only a fingerprint of it is kept, never
            the raw value. Evidence bundles are stored for a limited period
            (90 days) and then deleted; the resulting report and score are
            retained for as long as your account exists.
          </p>
          <p>
            Passive-tier scanning only ever makes requests a normal visitor
            or search-engine crawler would make. Active-tier scanning — path
            enumeration and deeper probing — only runs once we have verified
            you own or control the target, via a DNS record, a well-known
            file, or a meta tag you control.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Who we share data with</h2>
          <p>
            We use a small number of subprocessors to run the service:
            our cloud hosting and database provider, our email provider
            (for account and report notifications), our authentication
            provider (Clerk), our merchant-of-record billing provider, and
            an LLM provider used to generate plain-language remediation
            guidance for findings. Data sent to the LLM provider is limited
            to already-redacted finding summaries — never raw evidence or
            account credentials. We do not sell your data.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Your rights</h2>
          <p>
            You can request a copy of the data we hold about you, ask us to
            correct it, or ask us to delete your account and associated
            data, by emailing{" "}
            <a href={`mailto:${brand.supportEmail}`} className="underline">
              {brand.supportEmail}
            </a>
            . If you are a site owner and want a scan of your site removed
            or want your site excluded from future scanning regardless of
            who submits it, see our{" "}
            <Link href="/aup" className="underline">
              Acceptable Use Policy
            </Link>
            .
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
