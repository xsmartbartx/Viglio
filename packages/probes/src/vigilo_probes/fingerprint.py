"""Fingerprinting: signals derived from an already-captured HttpObservation.
No new network I/O — this is what makes it safe to run unconditionally on
every scan. The signal set is intentionally small in Phase 1; Phase 2's
`bundle`/`render` probes (JS bundle inspection, headless rendering) will add
much richer signals.
"""

from __future__ import annotations

from vigilo_core.evidence import FingerprintObservation, HttpObservation

_HOSTING_HEADER_SIGNALS = {
    "server": {
        "cloudflare": "cloudflare",
        "vercel": "vercel",
        "netlify": "netlify",
        "github.com": "github-pages",
        "amazons3": "aws-s3",
        "cloudfront": "aws-cloudfront",
    },
    "x-vercel-id": {"": "vercel"},
    "x-nf-request-id": {"": "netlify"},
    "x-github-request-id": {"": "github-pages"},
}

_FRAMEWORK_BODY_SIGNALS = {
    "__next_data__": "next.js",
    "/_next/static/": "next.js",
    "data-vite-": "vite",
    "/_astro/": "astro",
    "ng-version=": "angular",
    "data-reactroot": "react",
    "__nuxt__": "nuxt",
}


def fingerprint(http: HttpObservation | None) -> FingerprintObservation:
    """Pure function: `http` in, signal lists out."""
    if http is None:
        return FingerprintObservation()

    hosting: set[str] = set()
    for header_name, value_map in _HOSTING_HEADER_SIGNALS.items():
        header_value = http.headers.get(header_name)
        if header_value is None:
            continue
        for needle, label in value_map.items():
            if needle == "" or needle in header_value.lower():
                hosting.add(label)

    body_lower = http.body_excerpt.lower()
    frameworks = {
        label for needle, label in _FRAMEWORK_BODY_SIGNALS.items() if needle in body_lower
    }

    return FingerprintObservation(
        hosting_signals=sorted(hosting),
        framework_signals=sorted(frameworks),
    )
