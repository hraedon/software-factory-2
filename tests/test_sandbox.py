from __future__ import annotations

from factory.sandbox import (
    gate_subprocess_env,
    strip_sensitive_env,
)


class TestStripSensitiveEnv:
    def test_strips_exact_matches(self):
        env = {"PATH": "/bin", "DATABASE_URL": "postgres://user:pass@host/db", "HOME": "/home"}
        result = strip_sensitive_env(env)
        assert "DATABASE_URL" not in result
        assert result["PATH"] == "/bin"
        assert result["HOME"] == "/home"

    def test_strips_key_substring(self):
        env = {"PATH": "/bin", "API_KEY": "secret123", "HOME": "/home"}
        result = strip_sensitive_env(env)
        assert "API_KEY" not in result
        assert result["PATH"] == "/bin"

    def test_strips_secret_substring(self):
        env = {"MY_SECRET_VALUE": "xyz", "PATH": "/bin"}
        result = strip_sensitive_env(env)
        assert "MY_SECRET_VALUE" not in result

    def test_strips_token_substring(self):
        env = {"AUTH_TOKEN": "tok123", "PATH": "/bin"}
        result = strip_sensitive_env(env)
        assert "AUTH_TOKEN" not in result

    def test_strips_credential_substring(self):
        env = {"AWS_CREDENTIALS_FILE": "/tmp/creds", "PATH": "/bin"}
        result = strip_sensitive_env(env)
        assert "AWS_CREDENTIALS_FILE" not in result

    def test_strips_password_substring(self):
        env = {"DB_PASSWORD": "p4ss", "PATH": "/bin"}
        result = strip_sensitive_env(env)
        assert "DB_PASSWORD" not in result

    def test_strips_auth_substring(self):
        env = {"AUTHORIZATION_HEADER": "Bearer tok", "PATH": "/bin"}
        result = strip_sensitive_env(env)
        assert "AUTHORIZATION_HEADER" not in result

    def test_case_insensitive_matching(self):
        env = {"api_key": "val", "Secret_Code": "val", "MY_TOKEN": "val"}
        result = strip_sensitive_env(env)
        assert len(result) == 0

    def test_preserves_operational_vars(self):
        env = {
            "PATH": "/bin:/usr/bin",
            "HOME": "/home/user",
            "PYTHONPATH": "/src",
            "LANG": "en_US.UTF-8",
            "USER": "test",
            "SHELL": "/bin/bash",
        }
        result = strip_sensitive_env(env)
        assert result == env

    def test_defaults_to_os_environ(self, monkeypatch):
        monkeypatch.setenv("TEST_API_KEY", "should_be_stripped")
        monkeypatch.setenv("TEST_KEEP_ME", "safe")
        result = strip_sensitive_env()
        assert "TEST_API_KEY" not in result
        assert result["TEST_KEEP_ME"] == "safe"

    def test_empty_env(self):
        result = strip_sensitive_env({})
        assert result == {}

    def test_none_defaults_to_os_environ(self, monkeypatch):
        monkeypatch.setenv("SANDBOX_TEST_TOKEN", "strip_me")
        result = strip_sensitive_env(None)
        assert "SANDBOX_TEST_TOKEN" not in result


class TestGateSubprocessEnv:
    def test_adds_overrides(self, monkeypatch):
        monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
        env = gate_subprocess_env(PYTHONPATH="/tmp/test")
        assert env["PYTHONPATH"] == "/tmp/test"

    def test_overrides_are_not_sensitive(self, monkeypatch):
        monkeypatch.setenv("MY_API_KEY", "secret")
        env = gate_subprocess_env(PYTHONPATH="/tmp/test")
        assert "MY_API_KEY" not in env
        assert env["PYTHONPATH"] == "/tmp/test"

    def test_no_overrides(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("API_KEY", raising=False)
        env = gate_subprocess_env()
        assert "DATABASE_URL" not in env
        assert "PATH" in env

    def test_strips_credentials_yaml_path_not_in_env(self, monkeypatch):
        monkeypatch.setenv("CREDENTIALS_PATH", "/home/user/.config/factory/credentials.yaml")
        env = gate_subprocess_env()
        assert "CREDENTIALS_PATH" not in env

    def test_preserves_mypypath(self, monkeypatch):
        monkeypatch.delenv("MY_API_KEY", raising=False)
        env = gate_subprocess_env(MYPYPATH="/tmp/mypy")
        assert env["MYPYPATH"] == "/tmp/mypy"
