"""Tests for URL/content normalization, hashing, and domain extraction."""

import pytest
from app.research.processing.normalization import (
    normalize_url, normalize_content, hash_url, hash_content, extract_domain,
)


class TestURLNormalization:

    def test_lowercase_scheme_and_host(self):
        assert normalize_url("HTTP://WWW.EXAMPLE.COM/Path") == "https://example.com/Path"

    def test_strip_tracking_params(self):
        url = "https://example.com/page?utm_source=test&foo=bar&utm_medium=cpc"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "foo=bar" in result

    def test_strip_fragment(self):
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_strip_trailing_slash(self):
        assert normalize_url("https://example.com/page/") == "https://example.com/page"

    def test_keep_root_slash(self):
        result = normalize_url("https://example.com/")
        assert result.endswith("/")

    def test_strip_www(self):
        result = normalize_url("https://www.example.com/page")
        assert "www." not in result

    def test_strip_default_ports(self):
        assert "80" not in normalize_url("http://example.com:80/page")
        assert "443" not in normalize_url("https://example.com:443/page")

    def test_sort_query_params(self):
        result = normalize_url("https://example.com?z=1&a=2&m=3")
        assert "a=2" in result
        # 'a' should come before 'z'
        a_pos = result.index("a=2")
        z_pos = result.index("z=1")
        assert a_pos < z_pos

    def test_idempotent(self):
        url = "HTTPS://WWW.Example.COM/page?utm_source=x&id=1#anchor"
        once = normalize_url(url)
        twice = normalize_url(once)
        assert once == twice

    def test_empty_url(self):
        assert normalize_url("") == ""

    def test_force_https_for_known_domains(self):
        result = normalize_url("http://google.com/search")
        assert result.startswith("https://")


class TestContentNormalization:

    def test_strip_html(self):
        content = "<p>Hello <b>world</b></p>"
        result, _ = normalize_content(content)
        assert "<" not in result
        assert "Hello" in result and "world" in result

    def test_collapse_whitespace(self):
        content = "Hello    world\n\n\n\n\ntest"
        result, _ = normalize_content(content)
        assert "    " not in result

    def test_truncation(self):
        content = "x" * 10000
        result, truncated = normalize_content(content, max_length=8000)
        assert len(result) == 8000
        assert truncated is True

    def test_no_truncation(self):
        content = "short text"
        result, truncated = normalize_content(content)
        assert truncated is False

    def test_unicode_nfkc(self):
        # ﬁ (fi ligature) should normalize to "fi"
        content = "ﬁnance"
        result, _ = normalize_content(content)
        assert "fi" in result

    def test_empty_content(self):
        result, truncated = normalize_content("")
        assert result == ""
        assert truncated is False


class TestHashing:

    def test_url_hash_deterministic(self):
        h1 = hash_url("https://example.com/page")
        h2 = hash_url("https://example.com/page")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    def test_url_hash_sensitive(self):
        h1 = hash_url("https://example.com/page1")
        h2 = hash_url("https://example.com/page2")
        assert h1 != h2

    def test_content_hash_bounded_prefix(self):
        # Hash is based on first 4000 chars only
        base = "a" * 4000
        h1 = hash_content(base + "DIFFERENT1")
        h2 = hash_content(base + "DIFFERENT2")
        assert h1 == h2  # Tail differences don't matter

    def test_content_hash_sensitive_to_prefix(self):
        h1 = hash_content("content A ...")
        h2 = hash_content("content B ...")
        assert h1 != h2


class TestDomainExtraction:

    def test_basic(self):
        assert extract_domain("https://www.example.com/page") == "example.com"

    def test_subdomain(self):
        assert extract_domain("https://blog.example.com/post") == "blog.example.com"

    def test_no_www(self):
        assert extract_domain("https://example.com") == "example.com"

    def test_empty(self):
        assert extract_domain("") == ""
