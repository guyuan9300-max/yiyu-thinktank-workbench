from __future__ import annotations

import jwt
import pytest

from app.security import ALGORITHM, create_access_token, decode_access_token


SECRET = "test-secret-with-at-least-thirty-two-bytes"
WRONG_SECRET = "wrong-secret-with-at-least-thirty-two-bytes"


def test_access_token_round_trip_preserves_hs256_and_claims() -> None:
    token = create_access_token(
        SECRET,
        "user-123",
        extra={"organization_id": "org-456", "role": "admin"},
        expires_minutes=5,
    )

    assert jwt.get_unverified_header(token)["alg"] == ALGORITHM == "HS256"
    payload = decode_access_token(SECRET, token)
    assert payload["sub"] == "user-123"
    assert payload["organization_id"] == "org-456"
    assert payload["role"] == "admin"
    assert isinstance(payload["exp"], int)


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        jwt.encode({"sub": "user-123"}, WRONG_SECRET, algorithm="HS256"),
        jwt.encode({"sub": "user-123"}, SECRET * 2, algorithm="HS384"),
    ],
)
def test_access_token_rejects_malformed_wrong_secret_and_wrong_algorithm(token: str) -> None:
    with pytest.raises(ValueError, match="invalid token"):
        decode_access_token(SECRET, token)


def test_access_token_rejects_expired_token() -> None:
    token = create_access_token(SECRET, "user-123", expires_minutes=-1)

    with pytest.raises(ValueError, match="invalid token"):
        decode_access_token(SECRET, token)
