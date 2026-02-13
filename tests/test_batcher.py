"""Unit tests for batching utilities."""

from tools.batcher import infer_intent


class TestInferIntent:
    """Test cases for the infer_intent function."""

    def test_infer_button_from_key(self):
        """Test button detection from key name."""
        assert infer_intent("submit_button", "Submit") == "button"
        assert infer_intent("next_btn", "Next") == "button"
        assert infer_intent("cancel_cta", "Cancel") == "button"
        assert infer_intent("confirm_action", "Confirm") == "button"

    def test_infer_title_from_key(self):
        """Test title detection from key name."""
        assert infer_intent("modal_title", "Welcome") == "title"
        assert infer_intent("page_header", "Dashboard") == "title"
        assert infer_intent("section_headline", "Overview") == "title"

    def test_infer_error_from_key(self):
        """Test error detection from key name."""
        assert infer_intent("validation_error", "Invalid input") == "error"
        assert infer_intent("login_failed", "Login failed") == "error"
        assert infer_intent("field_required", "This field is required") == "error"

    def test_infer_label_from_key(self):
        """Test label detection from key name."""
        assert infer_intent("username_label", "Username") == "label"
        assert infer_intent("email_placeholder", "Enter email") == "label"
        assert infer_intent("password_hint", "8+ characters") == "label"

    def test_infer_tooltip_from_key(self):
        """Test tooltip detection from key name."""
        assert infer_intent("info_tooltip", "More information") == "tooltip"
        assert infer_intent("help_helper", "Need help?") == "tooltip"
        assert infer_intent("field_description", "Description here") == "tooltip"

    def test_infer_text_default(self):
        """Test default text intent for unmatched keys."""
        assert infer_intent("random_key", "Some text") == "text"
        assert infer_intent("content", "Content text") == "text"
        assert infer_intent("message", "A message") == "text"

    def test_infer_case_insensitive(self):
        """Test that key matching is case insensitive."""
        assert infer_intent("SUBMIT_BUTTON", "Submit") == "button"
        assert infer_intent("Modal_Title", "Title") == "title"
        assert infer_intent("ERROR_Message", "Error") == "error"

    def test_infer_with_complex_keys(self):
        """Test intent inference with complex key patterns."""
        assert infer_intent("auth.login.submit", "Login") == "button"
        assert infer_intent("form.validation.required", "Required") == "error"
        assert infer_intent("settings.modal.title", "Settings") == "title"
