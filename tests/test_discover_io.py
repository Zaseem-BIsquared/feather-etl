"""Unit tests for discover I/O helpers in feather_etl.config."""


class TestSanitize:
    def test_keeps_safe_chars(self):
        from feather_etl.config import _sanitize

        assert _sanitize("prod-erp.db_01") == "prod-erp.db_01"

    def test_replaces_unsafe_chars(self):
        from feather_etl.config import _sanitize

        assert _sanitize("prod/erp") == "prod_erp"
        assert _sanitize("192.168.2.62:1433") == "192.168.2.62_1433"
        assert _sanitize("a b c") == "a_b_c"

    def test_preserves_dots_and_hyphens(self):
        from feather_etl.config import _sanitize

        assert _sanitize("db.internal-prod") == "db.internal-prod"
