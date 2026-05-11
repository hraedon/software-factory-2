from __future__ import annotations

from factory.credentials import inject_credentials_into_env, redact_value


class TestRedactValue:
    def test_known_prefix_long(self):
        assert redact_value("fk-1234567890abcdef") == "fk-1********"

    def test_known_prefix_short_value(self):
        result = redact_value("fk-ab")
        assert "*" in result
        assert "fk-ab" not in result

    def test_known_prefix_four_chars(self):
        result = redact_value("fk-1")
        assert result == "********"

    def test_zai_prefix(self):
        assert redact_value("zai-abc123456789") == "zai-********"

    def test_sk_prefix(self):
        assert redact_value("sk-1234567890") == "sk-1********"

    def test_gsk_prefix(self):
        assert redact_value("gsk-abcdef123456") == "gsk-********"

    def test_pk_prefix(self):
        assert redact_value("pk-1234567890ab") == "pk-1********"

    def test_aiza_prefix(self):
        assert redact_value("AIzaSyD-1234567890") == "AIza********"

    def test_unknown_prefix_long(self):
        assert redact_value("abcdefghijklmnop") == "abcd********"

    def test_unknown_short(self):
        assert redact_value("abc") == "****"

    def test_unknown_eight_chars(self):
        result = redact_value("abcdefgh")
        assert "*" in result
        assert "abcdefgh" not in result

    def test_empty_string(self):
        assert redact_value("") == "****"


class TestInjectCredentialsEnvFootgun:
    def test_none_env_uses_os_environ(self):
        env = inject_credentials_into_env({}, "test")
        assert "PATH" in env

    def test_explicit_env_not_copied_from_os_environ(self):
        explicit = {"MY_VAR": "value"}
        env = inject_credentials_into_env({}, "test", env=explicit)
        assert env == {"MY_VAR": "value"}

    def test_empty_dict_does_not_copy_os_environ(self):
        env = inject_credentials_into_env({}, "test", env={})
        assert "PATH" not in env
        assert env == {}

    def test_credentials_merged_into_explicit_env(self):
        creds = {"provider_x": {"api_key": "sk-test1234567890"}}
        env = inject_credentials_into_env(creds, "provider_x", env={"MY_VAR": "val"})
        assert env["MY_VAR"] == "val"
        assert env["PROVIDER_X_API_KEY"] == "sk-test1234567890"

    def test_no_credentials_returns_env_unchanged(self):
        env = {"KEY": "val"}
        result = inject_credentials_into_env({}, "missing", env=env)
        assert result == {"KEY": "val"}
