# Check catalog

**Generated from `vigilo_checks.REGISTRY` — do not hand-edit.** Regenerate with `uv run python scripts/generate_check_catalog.py` after any manifest change (docs/build-roadmap.md Phase 2 exit criterion).

**64 checks** across 9 categories.

## CLI — Client-side exposure

| ID | Title | Severity | Confidence | Tier | Weight | Reference |
| --- | --- | --- | --- | --- | --- | --- |
| `VG-CLI-001` | No AWS access key in client bundle | critical | confirmed | passive | 9 | [link](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html) |
| `VG-CLI-002` | No live payment secret key in client bundle | critical | confirmed | passive | 10 | [link](https://docs.stripe.com/keys#safe-keys) |
| `VG-CLI-003` | No Slack token in client bundle | high | confirmed | passive | 7 | [link](https://api.slack.com/authentication/token-types) |
| `VG-CLI-004` | No GitHub/GitLab token in client bundle | critical | confirmed | passive | 9 | [link](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github) |
| `VG-CLI-005` | No private key embedded in client bundle | critical | confirmed | passive | 10 | [link](https://owasp.org/www-community/vulnerabilities/Use_of_hard-coded_password) |
| `VG-CLI-006` | No generic high-entropy secret in client bundle | medium | indicated | passive | 4 | [link](https://owasp.org/www-community/vulnerabilities/Use_of_hard-coded_password) |
| `VG-CLI-007` | No source map reference shipped to production | low | confirmed | passive | 2 | [link](https://developer.chrome.com/docs/devtools/javascript/source-maps) |
| `VG-CLI-008` | No development-mode build shipped to production | low | indicated | passive | 2 | [link](https://react.dev/reference/react-dom/client/hydrateRoot#minifying-and-avoiding-development-builds-in-production) |
| `VG-CLI-009` | Bounded console logging in production | info | indicated | passive | 1 | [link](https://owasp.org/www-project-web-security-testing-guide/) |
| `VG-CLI-010` | No hardcoded internal/staging hostname in client bundle | low | indicated | passive | 2 | [link](https://owasp.org/www-project-web-security-testing-guide/) |

## CMP — Compliance

| ID | Title | Severity | Confidence | Tier | Weight | Reference |
| --- | --- | --- | --- | --- | --- | --- |
| `VG-CMP-001` | Trackers are not loaded without a consent mechanism | medium | indicated | passive | 3 | [link](https://gdpr.eu/cookies/) |
| `VG-CMP-002` | Google Analytics uses Consent Mode | low | indicated | passive | 2 | [link](https://developers.google.com/tag-platform/security/guides/consent) |
| `VG-CMP-003` | No pre-checked marketing consent checkbox | medium | indicated | passive | 2 | [link](https://gdpr-info.eu/art-4-gdpr/) |
| `VG-CMP-004` | Consent notice references the privacy policy | low | indicated | passive | 1 | [link](https://gdpr.eu/cookies/) |

## DAT — Data platform posture

| ID | Title | Severity | Confidence | Tier | Weight | Reference |
| --- | --- | --- | --- | --- | --- | --- |
| `VG-DAT-001` | No backend service-role/admin key in client bundle | critical | confirmed | passive | 10 | [link](https://supabase.com/docs/guides/api/api-keys) |
| `VG-DAT-002` | Supabase REST schema is not publicly introspectable | high | indicated | passive | 7 | [link](https://supabase.com/docs/guides/database/postgres/row-level-security) |
| `VG-DAT-003` | Firebase Realtime Database is not publicly readable | critical | confirmed | passive | 10 | [link](https://firebase.google.com/docs/database/security) |
| `VG-DAT-004` | No publicly listable object storage bucket | high | confirmed | passive | 7 | [link](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html) |

## DEP — Dependencies

| ID | Title | Severity | Confidence | Tier | Weight | Reference |
| --- | --- | --- | --- | --- | --- | --- |
| `VG-DEP-001` | Third-party scripts use Subresource Integrity | medium | confirmed | passive | 4 | [link](https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity) |
| `VG-DEP-002` | No known end-of-life JS library version | medium | indicated | passive | 3 | [link](https://endoflife.date/) |
| `VG-DEP-003` | Bounded third-party script surface area | low | indicated | passive | 1 | [link](https://owasp.org/www-community/Third_Party_Javascript_Management) |
| `VG-DEP-004` | No unpinned 'latest' CDN script version | medium | indicated | passive | 3 | [link](https://slsa.dev/spec/v1.0/requirements) |

## EXP — Surface exposure

| ID | Title | Severity | Confidence | Tier | Weight | Reference |
| --- | --- | --- | --- | --- | --- | --- |
| `VG-EXP-001` | security.txt is present | low | confirmed | passive | 1 | [link](https://www.rfc-editor.org/rfc/rfc9116) |
| `VG-EXP-002` | robots.txt is present | info | confirmed | passive | 0 | [link](https://developers.google.com/search/docs/crawling-indexing/robots/intro) |
| `VG-EXP-003` | sitemap.xml is present | info | confirmed | passive | 0 | [link](https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview) |
| `VG-EXP-004` | Web app manifest is present | info | confirmed | passive | 0 | [link](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest) |
| `VG-EXP-005` | No verbose error page on the homepage | high | confirmed | passive | 6 | [link](https://owasp.org/www-project-top-ten/2017/A6_2017-Security_Misconfiguration) |
| `VG-EXP-006` | Repository metadata not exposed | critical | confirmed | active | 9 | [link](https://cwe.mitre.org/data/definitions/527.html) |
| `VG-EXP-007` | No backup or archive files reachable | critical | confirmed | active | 9 | [link](https://cwe.mitre.org/data/definitions/530.html) |
| `VG-EXP-008` | No exposed configuration files | critical | confirmed | active | 9 | [link](https://cwe.mitre.org/data/definitions/538.html) |
| `VG-EXP-009` | No debug routes reachable | medium | confirmed | active | 5 | [link](https://cwe.mitre.org/data/definitions/215.html) |
| `VG-EXP-010` | No test/staging routes reachable | low | indicated | active | 3 | [link](https://cwe.mitre.org/data/definitions/489.html) |
| `VG-EXP-011` | No directory listing enabled | medium | indicated | active | 5 | [link](https://cwe.mitre.org/data/definitions/548.html) |
| `VG-EXP-012` | No default admin panel paths exposed | low | indicated | active | 2 | [link](https://owasp.org/Top10/A05_2021-Security_Misconfiguration/) |

## HDR — Response headers

| ID | Title | Severity | Confidence | Tier | Weight | Reference |
| --- | --- | --- | --- | --- | --- | --- |
| `VG-HDR-001` | HSTS enforced | high | confirmed | passive | 8 | [link](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security) |
| `VG-HDR-002` | HSTS max-age is long enough | medium | confirmed | passive | 4 | [link](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security) |
| `VG-HDR-003` | HSTS covers subdomains | low | confirmed | passive | 2 | [link](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security) |
| `VG-HDR-004` | Content-Security-Policy present | high | confirmed | passive | 7 | [link](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy) |
| `VG-HDR-005` | CSP forbids unsafe-inline scripts | medium | indicated | passive | 4 | [link](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/script-src) |
| `VG-HDR-006` | MIME-sniffing protection | low | confirmed | passive | 2 | [link](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options) |
| `VG-HDR-007` | Clickjacking protection | medium | confirmed | passive | 4 | [link](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options) |
| `VG-HDR-008` | Referrer-Policy is set and safe | low | confirmed | passive | 2 | [link](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy) |
| `VG-HDR-009` | Permissions-Policy present | low | confirmed | passive | 1 | [link](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Permissions-Policy) |
| `VG-HDR-010` | Server header doesn't disclose a version | info | indicated | passive | 1 | [link](https://owasp.org/www-project-web-security-testing-guide/) |
| `VG-HDR-011` | X-Powered-By is absent | info | confirmed | passive | 1 | [link](https://owasp.org/www-project-secure-headers/) |
| `VG-HDR-012` | Content-Type is present | low | confirmed | passive | 1 | [link](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type) |

## LEG — Legal documents

| ID | Title | Severity | Confidence | Tier | Weight | Reference |
| --- | --- | --- | --- | --- | --- | --- |
| `VG-LEG-001` | Privacy policy is linked | medium | indicated | passive | 3 | [link](https://gdpr-info.eu/art-13-gdpr/) |
| `VG-LEG-002` | Terms of service is linked | low | indicated | passive | 2 | [link](https://www.ftc.gov/business-guidance) |
| `VG-LEG-003` | Cookie policy is linked | low | indicated | passive | 2 | [link](https://gdpr.eu/cookies/) |
| `VG-LEG-004` | Contact information is present | low | indicated | passive | 1 | [link](https://gdpr-info.eu/art-13-gdpr/) |

## SES — Cookies & sessions

| ID | Title | Severity | Confidence | Tier | Weight | Reference |
| --- | --- | --- | --- | --- | --- | --- |
| `VG-SES-001` | Cookies use the Secure attribute | high | confirmed | passive | 6 | [link](https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies#restrict_access_to_cookies) |
| `VG-SES-002` | Cookies use the HttpOnly attribute | high | confirmed | passive | 6 | [link](https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies#restrict_access_to_cookies) |
| `VG-SES-003` | Cookies set SameSite explicitly | low | confirmed | passive | 2 | [link](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite) |
| `VG-SES-004` | SameSite=None cookies are also Secure | medium | confirmed | passive | 3 | [link](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite#none) |
| `VG-SES-005` | Session identifiers are not exposed in URLs | medium | indicated | passive | 3 | [link](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) |
| `VG-SES-006` | Session cookie lifetime is sane | low | indicated | passive | 2 | [link](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) |

## TLS — Transport & TLS

| ID | Title | Severity | Confidence | Tier | Weight | Reference |
| --- | --- | --- | --- | --- | --- | --- |
| `VG-TLS-001` | HTTPS is enforced | critical | confirmed | passive | 10 | [link](https://developer.mozilla.org/en-US/docs/Web/Security/Transport_Layer_Security) |
| `VG-TLS-002` | TLS certificate chain verifies | critical | confirmed | passive | 10 | [link](https://developer.mozilla.org/en-US/docs/Web/Security/Transport_Layer_Security) |
| `VG-TLS-003` | Certificate is not expired | critical | confirmed | passive | 10 | [link](https://developer.mozilla.org/en-US/docs/Web/Security/Transport_Layer_Security) |
| `VG-TLS-004` | Certificate is not about to expire | medium | confirmed | passive | 3 | [link](https://developer.mozilla.org/en-US/docs/Web/Security/Transport_Layer_Security) |
| `VG-TLS-005` | TLS protocol version is 1.2 or higher | high | confirmed | passive | 6 | [link](https://www.rfc-editor.org/rfc/rfc8996) |
| `VG-TLS-006` | No mixed content | medium | indicated | passive | 3 | [link](https://developer.mozilla.org/en-US/docs/Web/Security/Mixed_content) |
| `VG-TLS-007` | Certificate validity window follows the CA/Browser Forum baseline | low | confirmed | passive | 2 | [link](https://cabforum.org/baseline-requirements/) |
| `VG-TLS-008` | No legacy-weak cipher negotiated | high | confirmed | passive | 5 | [link](https://developer.mozilla.org/en-US/docs/Web/Security/Transport_Layer_Security) |
