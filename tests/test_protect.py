"""Unit tests for placeholder protection/unprotection."""

from tools.protect import protect, unprotect

# Expected counts for test assertions
EXPECTED_PLACEHOLDERS_SIMPLE = 2
EXPECTED_PLACEHOLDERS_COMPLEX = 4


class TestProtect:
    """Test cases for the protect function."""

    def test_protect_no_tokens(self):
        """Test string without any tokens."""
        text = "Hello world"
        protected, mapping = protect(text)
        assert protected == "Hello world"
        assert mapping == {}

    def test_protect_curly_braces(self):
        """Test protection of {variable} tokens."""
        text = "Hello {name}, you have {count} messages"
        protected, mapping = protect(text)
        assert "__PH_0__" in protected
        assert "__PH_1__" in protected
        assert len(mapping) == EXPECTED_PLACEHOLDERS_SIMPLE
        assert mapping["__PH_0__"] == "{name}"
        assert mapping["__PH_1__"] == "{count}"

    def test_protect_double_curly(self):
        """Test protection of {{variable}} tokens."""
        text = "Welcome {{user}}"
        protected, mapping = protect(text)
        assert "__PH_0__" in protected
        assert mapping["__PH_0__"] == "{{user}}"

    def test_protect_html_tags(self):
        """Test protection of HTML tags."""
        text = "Click <b>here</b> to continue"
        protected, mapping = protect(text)
        assert "__PH_0__" in protected
        assert "__PH_1__" in protected
        assert mapping["__PH_0__"] == "<b>"
        assert mapping["__PH_1__"] == "</b>"

    def test_protect_printf_style(self):
        """Test protection of printf-style tokens."""
        text = "User %s has %d items"
        protected, mapping = protect(text)
        assert len(mapping) == EXPECTED_PLACEHOLDERS_SIMPLE
        assert "%s" in mapping.values()
        assert "%d" in mapping.values()

    def test_protect_mixed_tokens(self):
        """Test protection of multiple token types."""
        text = "Hello {{name}}, click <b>here</b> for {count} items"
        protected, mapping = protect(text)
        assert len(mapping) == EXPECTED_PLACEHOLDERS_COMPLEX
        assert all(f"__PH_{i}__" in protected for i in range(EXPECTED_PLACEHOLDERS_COMPLEX))


class TestUnprotect:
    """Test cases for the unprotect function."""

    def test_unprotect_empty_mapping(self):
        """Test unprotect with no placeholders."""
        text = "Hello world"
        result = unprotect(text, {})
        assert result == "Hello world"

    def test_unprotect_restores_tokens(self):
        """Test that unprotect correctly restores original tokens."""
        original = "Hello {name}, you have {count} messages"
        protected, mapping = protect(original)
        restored = unprotect(protected, mapping)
        assert restored == original

    def test_unprotect_order_independence(self):
        """Test that unprotect works regardless of placeholder order."""
        text = "__PH_1__ is before __PH_0__"
        mapping = {"__PH_0__": "{first}", "__PH_1__": "{second}"}
        result = unprotect(text, mapping)
        assert result == "{second} is before {first}"

    def test_protect_unprotect_roundtrip(self):
        """Test that protect->unprotect is a no-op."""
        original = "Complex string with {{var}}, <b>tags</b>, and {placeholders}"
        protected, mapping = protect(original)
        restored = unprotect(protected, mapping)
        assert restored == original

    def test_unprotect_html_roundtrip(self):
        """Test HTML tag roundtrip."""
        original = "<div>Content with <strong>bold</strong> text</div>"
        protected, mapping = protect(original)
        restored = unprotect(protected, mapping)
        assert restored == original
