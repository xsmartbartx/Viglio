import Link from "next/link";
import { DraftBanner } from "../../components/DraftBanner";
import { Footer } from "../../components/Footer";
import { brand } from "../../lib/brand";

export const metadata = { title: `Terms of Service — ${brand.name}` };

export default function TermsOfServicePage() {
  return (
    <>
      <DraftBanner />
      <main className="flex-1 mx-auto w-full max-w-2xl px-6 py-12 space-y-6">
        <div>
          <Link href="/" className="text-sm hover:underline">
            &larr; Back to {brand.name}
          </Link>
          <h1 className="mt-4 text-2xl font-bold">Terms of Service</h1>
          <p className="mt-1 text-sm text-black/60 dark:text-white/60">
            Last updated: September 2026
          </p>
        </div>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">The service</h2>
          <p>
            {brand.name} scans web applications for security and compliance
            issues and reports what it finds. By submitting a URL or
            creating an account, you agree to these terms.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Two tiers of scanning</h2>
          <p>
            <strong>Passive tier</strong> is available to anyone: it makes
            only the kind of requests an ordinary visitor or search-engine
            crawler would make against a publicly reachable URL.{" "}
            <strong>Active tier</strong> — including endpoint enumeration and
            deeper probing — is only performed once you have proven, via a
            DNS record, a well-known file, or a meta tag, that you control
            the target. Requesting active tier without a valid proof does
            not fail your scan; it is silently run at passive tier instead.
          </p>
          <p>
            You may only request active-tier scanning of sites you own or
            are authorized to test. Passive-tier scanning of a third-party
            site does not require the site owner's consent, but a site
            owner may have their site excluded from scanning at any time —
            see our{" "}
            <Link href="/aup" className="underline">
              Acceptable Use Policy
            </Link>
            .
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Plans and billing</h2>
          <p>
            {brand.name} offers a free plan with limited scans and targets,
            and paid plans with higher limits and additional features.
            Paid plans are billed by our merchant-of-record payment
            provider on a recurring basis until canceled. Downgrading or
            canceling takes effect at the end of the current billing
            period; your account's entitlements are updated automatically
            once the change is confirmed by our billing provider.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">No warranty</h2>
          <p>
            {brand.name} is provided on an "as is" basis. A passing report
            is not a guarantee that a site is free of security or
            compliance issues — our checks detect a defined set of known
            patterns and are one input into your own judgment, not a
            substitute for it. We are not liable for actions you take, or
            fail to take, based on a report.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Acceptable use</h2>
          <p>
            You agree not to use {brand.name} to scan targets you are not
            authorized to test at active tier, to attempt to circumvent
            rate limits or authorization checks, or to use the service in a
            way that disrupts it for other users. See our{" "}
            <Link href="/aup" className="underline">
              Acceptable Use Policy
            </Link>{" "}
            for the full policy.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Changes to these terms</h2>
          <p>
            We may update these terms as the service evolves. Material
            changes will be reflected on this page with an updated date.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Contact</h2>
          <p>
            Questions about these terms can be sent to{" "}
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
