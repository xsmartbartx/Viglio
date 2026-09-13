"""The generic adapter dispatcher docs/modules.md §7 documents
(`call(adapter_id, request) -> response`). Satisfies that documented API;
real callers in `packages/orchestrator` use the typed functions in
`mail.py`/`storage.py` directly — this exists for callers that need
stringly-typed dispatch (e.g. a future billing-webhook router in Phase 7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vigilo_core.errors import ErrorCode, StructuredError


@dataclass(frozen=True)
class AdapterRequest:
    operation: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterResponse:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)


async def call(adapter_id: str, request: AdapterRequest) -> AdapterResponse:
    from vigilo_integrations import mail, storage

    if adapter_id == "mail" and request.operation == "send_transactional_email":
        await mail.send_transactional_email(**request.payload)
        return AdapterResponse(ok=True)

    if adapter_id == "storage" and request.operation == "put_evidence_bundle":
        await storage.put_evidence_bundle(**request.payload)
        return AdapterResponse(ok=True)

    if adapter_id == "storage" and request.operation == "get_evidence_bundle":
        content = await storage.get_evidence_bundle(**request.payload)
        return AdapterResponse(ok=True, data={"content": content})

    raise StructuredError(
        ErrorCode.VALIDATION_ERROR,
        "unknown adapter operation",
        adapter_id=adapter_id,
        operation=request.operation,
    )
