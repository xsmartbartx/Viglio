"""Tests the actual JWT verification logic (signature, expiry, claim
extraction) against a locally-generated RSA keypair — never a live Clerk
instance, via the `get_signing_key` injection seam.
"""

from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from vigilo_api.auth import ClerkAuthError, verify_clerk_jwt

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()


def _make_token(**claims) -> str:
    payload = {"sub": "user_123", "iat": int(time.time()), "exp": int(time.time()) + 3600, **claims}
    return jwt.encode(payload, _PRIVATE_KEY, algorithm="RS256")


def _fake_get_signing_key(token: str):
    return _PUBLIC_KEY


def test_verifies_a_well_formed_token():
    token = _make_token(email="owner@example.com")

    claims = verify_clerk_jwt(token, get_signing_key=_fake_get_signing_key)

    assert claims.user_id == "user_123"
    assert claims.email == "owner@example.com"


def test_a_token_with_no_email_claim_is_still_valid():
    token = _make_token()

    claims = verify_clerk_jwt(token, get_signing_key=_fake_get_signing_key)

    assert claims.email is None


def test_an_expired_token_is_rejected():
    payload = {"sub": "user_123", "iat": int(time.time()) - 7200, "exp": int(time.time()) - 3600}
    token = jwt.encode(payload, _PRIVATE_KEY, algorithm="RS256")

    with pytest.raises(ClerkAuthError):
        verify_clerk_jwt(token, get_signing_key=_fake_get_signing_key)


def test_a_token_signed_by_a_different_key_is_rejected():
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    payload = {"sub": "user_123", "iat": int(time.time()), "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, other_key, algorithm="RS256")

    with pytest.raises(ClerkAuthError):
        verify_clerk_jwt(token, get_signing_key=_fake_get_signing_key)


def test_a_token_missing_the_subject_claim_is_rejected():
    payload = {"iat": int(time.time()), "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, _PRIVATE_KEY, algorithm="RS256")

    with pytest.raises(ClerkAuthError):
        verify_clerk_jwt(token, get_signing_key=_fake_get_signing_key)
