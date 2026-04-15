from __future__ import annotations

from src.auth import AuthService, AuthValidationError


def test_auth_register_and_authenticate(tmp_path):
    auth_service = AuthService(tmp_path / "users.db", min_password_length=8)

    user = auth_service.register_user(
        email="lawyer@example.com",
        password="SecurePass123",
        full_name="Asha Menon",
    )
    assert user.email == "lawyer@example.com"
    assert user.full_name == "Asha Menon"

    authenticated = auth_service.authenticate("lawyer@example.com", "SecurePass123")
    assert authenticated is not None
    assert authenticated.email == "lawyer@example.com"


def test_auth_rejects_duplicate_or_short_password(tmp_path):
    auth_service = AuthService(tmp_path / "users.db", min_password_length=8)
    auth_service.register_user(email="user@example.com", password="SecurePass123", full_name="First User")

    try:
        auth_service.register_user(email="user@example.com", password="SecurePass123", full_name="Second User")
        raise AssertionError("Duplicate email should have failed.")
    except AuthValidationError:
        pass


def test_auth_persistent_session_round_trip(tmp_path):
    auth_service = AuthService(tmp_path / "users.db", min_password_length=8)
    user = auth_service.register_user(
        email="persistent@example.com",
        password="SecurePass123",
        full_name="Persistent User",
    )

    session_token = auth_service.create_session(user.user_id, duration_days=14)
    restored = auth_service.get_user_by_session_token(session_token)

    assert restored is not None
    assert restored.email == "persistent@example.com"

    auth_service.revoke_session(session_token)
    assert auth_service.get_user_by_session_token(session_token) is None

    try:
        auth_service.register_user(email="new@example.com", password="short", full_name="Short Password")
        raise AssertionError("Short password should have failed.")
    except AuthValidationError:
        pass
