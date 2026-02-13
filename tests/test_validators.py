"""Unit tests for validation functions."""

from tools.validators import check_keys, check_tokens


class TestCheckKeys:
    """Test cases for key validation."""

    def test_check_keys_identical(self):
        """Test validation passes with identical keys."""
        src = {"a": "value1", "b": "value2"}
        dst = {"a": "traducción1", "b": "traducción2"}
        assert check_keys(src, dst) is True

    def test_check_keys_missing_in_dst(self, capsys):
        """Test validation fails when destination is missing keys."""
        src = {"a": "value1", "b": "value2", "c": "value3"}
        dst = {"a": "traducción1"}
        assert check_keys(src, dst) is False
        captured = capsys.readouterr()
        assert "Missing keys" in captured.out
        assert "b" in captured.out
        assert "c" in captured.out

    def test_check_keys_extra_in_dst(self, capsys):
        """Test validation fails when destination has extra keys."""
        src = {"a": "value1"}
        dst = {"a": "traducción1", "b": "extra", "c": "also_extra"}
        assert check_keys(src, dst) is False
        captured = capsys.readouterr()
        assert "extra keys" in captured.out
        assert "b" in captured.out
        assert "c" in captured.out

    def test_check_keys_nested_structure(self):
        """Test key validation with nested structures."""
        src = {"level1": {"level2": "value"}}
        dst = {"level1": {"level2": "traducción"}}
        assert check_keys(src, dst) is True

    def test_check_keys_array_structure(self):
        """Test key validation with array structures."""
        src = {"items": ["item1", "item2", "item3"]}
        dst = {"items": ["traducción1", "traducción2", "traducción3"]}
        assert check_keys(src, dst) is True


class TestCheckTokens:
    """Test cases for token validation."""

    def test_check_tokens_no_placeholders(self):
        """Test validation passes when no placeholders present."""
        src = {"greeting": "Hello world"}
        dst = {"greeting": "Hola mundo"}
        assert check_tokens(src, dst) is True

    def test_check_tokens_matching_placeholders(self):
        """Test validation passes with matching placeholders."""
        src = {"message": "Hello {name}, you have {count} items"}
        dst = {"message": "Hola {name}, tienes {count} elementos"}
        assert check_tokens(src, dst) is True

    def test_check_tokens_missing_placeholder(self, capsys):
        """Test validation fails when placeholder is missing."""
        src = {"message": "Hello {name}"}
        dst = {"message": "Hola"}
        assert check_tokens(src, dst) is False
        captured = capsys.readouterr()
        assert "placeholder mismatch" in captured.out
        assert "missing" in captured.out

    def test_check_tokens_extra_placeholder(self, capsys):
        """Test validation fails with unexpected placeholder."""
        src = {"message": "Hello"}
        dst = {"message": "Hola {name}"}
        assert check_tokens(src, dst) is False
        captured = capsys.readouterr()
        assert "placeholder mismatch" in captured.out

    def test_check_tokens_html_tags(self):
        """Test validation with HTML tags."""
        src = {"text": "Click <b>here</b>"}
        dst = {"text": "Haz clic <b>aquí</b>"}
        assert check_tokens(src, dst) is True

    def test_check_tokens_double_curly(self):
        """Test validation with double curly braces."""
        src = {"welcome": "Welcome {{user}}"}
        dst = {"welcome": "Bienvenido {{user}}"}
        assert check_tokens(src, dst) is True

    def test_check_tokens_printf_style(self):
        """Test validation with printf-style placeholders."""
        src = {"info": "User %s has %d items"}
        dst = {"info": "Usuario %s tiene %d elementos"}
        assert check_tokens(src, dst) is True

    def test_check_tokens_wrong_count(self, capsys):
        """Test validation fails with wrong placeholder count."""
        src = {"text": "{a} and {b}"}
        dst = {"text": "{a} solamente"}
        assert check_tokens(src, dst) is False

    def test_check_tokens_nested_structure(self):
        """Test token validation with nested structures."""
        src = {"form": {"name": "Name: {value}", "email": "Email: {value}"}}
        dst = {"form": {"name": "Nombre: {value}", "email": "Correo: {value}"}}
        assert check_tokens(src, dst) is True

    def test_check_tokens_non_string_value(self, capsys):
        """Test validation handles non-string values."""
        src = {"key": "value"}
        dst = {"key": 123}
        assert check_tokens(src, dst) is False
        captured = capsys.readouterr()
        assert "expected string" in captured.out
