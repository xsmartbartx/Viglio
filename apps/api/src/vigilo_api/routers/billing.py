"""`POST /v1/billing/checkout` + `POST /v1/billing/webhook` (Phase 7).

The webhook route is deliberately public — Paddle authenticates itself via
`verify_webhook_signature()`, not a bearer token, so this reads the raw
request body directly rather than taking a parsed Pydantic model (signature
verification needs the exact bytes Paddle signed). An unrecognized event
type or an account that doesn't exist yet both return `200`/no-op rather
than an error — avoids provider retry storms, matching Paddle's own
expected webhook behavior.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from vigilo_api.deps import AccountDep, SessionDep
from vigilo_api.schemas import CheckoutRequest, CheckoutResponse
from vigilo_billing import UnrecognizedWebhookEvent, interpret_webhook_event
from vigilo_identity.repository import get_account_by_email, upsert_subscription
from vigilo_integrations.billing import (
    create_checkout_url,
    parse_webhook_event,
    verify_webhook_signature,
)
from vigilo_security.audit import AuditEvent, audit

router = APIRouter(prefix="/v1/billing", tags=["billing"])


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(body: CheckoutRequest, account: AccountDep) -> CheckoutResponse:
    checkout_url = create_checkout_url(body.plan_id, account.email, str(account.id))
    return CheckoutResponse(checkout_url=checkout_url)


@router.post("/webhook")
async def receive_webhook(request: Request, session: SessionDep) -> dict[str, str]:
    raw_body = await request.body()
    signature = request.headers.get("Paddle-Signature", "")

    if not verify_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    payload = parse_webhook_event(raw_body)

    try:
        event = interpret_webhook_event(payload)
    except UnrecognizedWebhookEvent:
        return {"status": "ignored"}

    account = await get_account_by_email(session, event.account_email)
    if account is None:
        return {"status": "ignored"}

    await upsert_subscription(
        session,
        account_id=account.id,
        plan_id=event.plan_id,
        status=event.status,
        provider=event.provider,
        provider_subscription_id=event.provider_subscription_id,
        current_period_end=event.period_end,
    )
    await audit(
        session,
        AuditEvent(
            actor="paddle",
            action="subscription_updated",
            subject=event.provider_subscription_id,
            account_id=account.id,
            metadata={"plan_id": event.plan_id, "status": event.status},
        ),
    )

    return {"status": "applied"}
