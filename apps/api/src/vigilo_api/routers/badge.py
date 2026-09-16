"""`GET /badge/{target_id}.svg` — the embeddable score badge (Phase 8).
Deliberately public, no `/v1` prefix — meant to be embedded cross-origin
via a plain `<img>` tag on the target owner's own site, same
`brand.config.json` `namespaces.badgePath` convention.

Reuses `Target.id` directly as the path segment rather than adding a new
`public_id` column: Phase 4 already established "an unguessable UUID is
already a de facto share link" for report PDFs
(`apps/api/src/vigilo_api/routers/reports.py`'s module docstring), and the
same reasoning applies here — a documented deviation from the literal
`{public_id}` placeholder name, not an oversight.

Contains no finding data by construction — `render_badge()`'s signature
only ever takes a `Score` and a timestamp (see `docs/security.md`).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from vigilo_api.deps import SessionDep
from vigilo_core.models import Score
from vigilo_orchestrator.service import list_scans_for_target
from vigilo_reporting import render_badge

router = APIRouter(tags=["badge"])

_CACHE_CONTROL = "public, max-age=3600"


@router.get("/badge/{target_id}.svg")
async def get_target_badge(target_id: uuid.UUID, session: SessionDep) -> Response:
    scans = await list_scans_for_target(session, target_id, limit=1)
    if not scans:
        raise HTTPException(status_code=404, detail="no scan yet for this target")

    scan = scans[0]
    score = Score(
        value=scan.score,
        grade=scan.grade,
        registry_version=scan.registry_version,
        counts_by_severity=scan.counts_by_severity,
    )
    svg = render_badge(score, scan.created_at)

    return Response(
        content=svg, media_type="image/svg+xml", headers={"Cache-Control": _CACHE_CONTROL}
    )
