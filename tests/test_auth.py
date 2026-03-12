"""Tests for authentication module."""

from src.auth import authenticate, Role


class TestAuthentication:
    def test_valid_admin_login(self):
        user = authenticate("admin", "admin123")
        assert user is not None
        assert user.username == "admin"
        assert user.role == Role.ADMIN
        assert user.display_name == "Admin"

    def test_valid_engineer_login(self):
        user = authenticate("torri", "Welcome123")
        assert user is not None
        assert user.username == "torri"
        assert user.role == Role.ENGINEER

    def test_all_engineers_exist(self):
        for name in ("torri", "danita", "shonda", "abhishek", "praveen"):
            user = authenticate(name, "Welcome123")
            assert user is not None, f"Engineer {name} should authenticate"
            assert user.role == Role.ENGINEER

    def test_case_insensitive_username(self):
        user = authenticate("Admin", "admin123")
        assert user is not None
        assert user.username == "admin"

    def test_invalid_password(self):
        user = authenticate("admin", "wrongpassword")
        assert user is None

    def test_nonexistent_user(self):
        user = authenticate("nobody", "password")
        assert user is None

    def test_empty_credentials(self):
        assert authenticate("", "") is None

    def test_admin_role_properties(self):
        user = authenticate("admin", "admin123")
        assert user.role == Role.ADMIN
        assert user.email == "admin@operationhope.org"

    def test_engineer_role_properties(self):
        user = authenticate("abhishek", "Welcome123")
        assert user.role == Role.ENGINEER
        assert user.email == "abhishek@operationhope.org"
