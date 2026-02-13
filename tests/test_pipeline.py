"""Integration tests for TranslationPipeline with mocks."""

import json
from typing import Dict, Iterable

import pytest
from tools.interfaces import Message
from tools.pipeline import PipelineConfig, TranslationPipeline


class MockLLMClient:
    """Mock LLM client for testing."""

    EXPECTED_MESSAGE_COUNT = 2  # System + user messages

    def __init__(self, model: str = "mock-model"):
        self._model = model
        self._call_count = 0

    @property
    def model(self) -> str:
        return self._model

    def complete(self, messages: Iterable[Message]) -> Dict[str, str]:
        """Mock completion that returns simple translations."""
        self._call_count += 1

        # Parse the user message to extract keys
        messages_list = list(messages)
        if len(messages_list) < self.EXPECTED_MESSAGE_COUNT:
            return {}

        user_content = messages_list[1].get("content", "{}")
        try:
            context = json.loads(user_content)
            batch = context.get("batch", [])

            # Return mock translations
            result = {}
            for item in batch:
                key = item.get("key")
                en_value = item.get("en", "")
                if key:
                    # Simple mock: just add " [translated]" suffix
                    result[key] = f"{en_value} [translated]"

            return result
        except Exception:
            return {}


@pytest.fixture
def temp_dir(tmp_path):
    """Create temporary directory for test files."""
    return tmp_path


@pytest.fixture
def mock_client():
    """Provide a mock LLM client."""
    return MockLLMClient()


@pytest.fixture
def pipeline_config(temp_dir):
    """Provide a basic pipeline configuration."""
    # Create minimal required files
    glossary_path = temp_dir / "glossary.yml"
    glossary_path.write_text("test: prueba\n", encoding="utf-8")

    system_prompt_path = temp_dir / "system.txt"
    system_prompt_path.write_text(
        "You are a translator. Translate to <<TARGET_LANGUAGE_NAME>>.", encoding="utf-8"
    )

    fewshot_path = temp_dir / "fewshot.json"
    fewshot_path.write_text("[]", encoding="utf-8")

    cache_file = temp_dir / "cache.json"

    return PipelineConfig(
        locale="es",
        batch_size=10,
        batch_max_attempts=2,
        min_delay_seconds=0,
        retry_delay_seconds=0,
        glossary_path=glossary_path,
        system_prompt_path=system_prompt_path,
        fewshot_path=fewshot_path,
        show_progress=False,
        cache_file=cache_file,
        use_cache=False,
    )


class TestTranslationPipeline:
    """Integration tests for TranslationPipeline."""

    def test_basic_translation(self, mock_client, pipeline_config, temp_dir):
        """Test basic translation workflow."""
        # Create source files
        en_data = {"greeting": "Hello", "farewell": "Goodbye"}
        ru_data = {"greeting": "Привет", "farewell": "До свидания"}

        en_path = temp_dir / "en.json"
        ru_path = temp_dir / "ru.json"
        dst_path = temp_dir / "es.json"

        en_path.write_text(json.dumps(en_data, ensure_ascii=False), encoding="utf-8")
        ru_path.write_text(json.dumps(ru_data, ensure_ascii=False), encoding="utf-8")

        # Run pipeline
        pipeline = TranslationPipeline(mock_client, pipeline_config)
        result = pipeline.run(en_path, ru_path, dst_path)

        # Verify
        assert "greeting" in result
        assert "farewell" in result
        assert dst_path.exists()

        # Check that output contains translations
        output = json.loads(dst_path.read_text(encoding="utf-8"))
        assert set(output.keys()) == {"greeting", "farewell"}

    def test_nested_structure(self, mock_client, pipeline_config, temp_dir):
        """Test translation with nested structures."""
        en_data = {
            "auth": {"login": "Login", "logout": "Logout"},
            "errors": {"required": "Required field"},
        }
        ru_data = {
            "auth": {"login": "Войти", "logout": "Выйти"},
            "errors": {"required": "Обязательное поле"},
        }

        en_path = temp_dir / "en.json"
        ru_path = temp_dir / "ru.json"
        dst_path = temp_dir / "es.json"

        en_path.write_text(json.dumps(en_data, ensure_ascii=False), encoding="utf-8")
        ru_path.write_text(json.dumps(ru_data, ensure_ascii=False), encoding="utf-8")

        pipeline = TranslationPipeline(mock_client, pipeline_config)
        result = pipeline.run(en_path, ru_path, dst_path)

        # Verify structure is preserved
        assert "auth" in result
        assert "login" in result["auth"]
        assert "logout" in result["auth"]
        assert "errors" in result
        assert "required" in result["errors"]

    def test_with_placeholders(self, mock_client, pipeline_config, temp_dir):
        """Test translation with placeholders."""
        en_data = {"greeting": "Hello {name}", "count": "You have {count} items"}
        ru_data = {"greeting": "Привет {name}", "count": "У вас {count} элементов"}

        en_path = temp_dir / "en.json"
        ru_path = temp_dir / "ru.json"
        dst_path = temp_dir / "es.json"

        en_path.write_text(json.dumps(en_data, ensure_ascii=False), encoding="utf-8")
        ru_path.write_text(json.dumps(ru_data, ensure_ascii=False), encoding="utf-8")

        pipeline = TranslationPipeline(mock_client, pipeline_config)
        result = pipeline.run(en_path, ru_path, dst_path)

        # Verify placeholders are preserved
        assert "{name}" in result["greeting"]
        assert "{count}" in result["count"]

    def test_caching(self, mock_client, temp_dir):
        """Test that caching works correctly."""
        # Create config with cache enabled
        glossary_path = temp_dir / "glossary.yml"
        glossary_path.write_text("", encoding="utf-8")

        system_prompt_path = temp_dir / "system.txt"
        system_prompt_path.write_text("Translate to <<TARGET_LANGUAGE_NAME>>.", encoding="utf-8")

        fewshot_path = temp_dir / "fewshot.json"
        fewshot_path.write_text("[]", encoding="utf-8")

        cache_file = temp_dir / "cache.json"

        config = PipelineConfig(
            locale="es",
            batch_size=10,
            batch_max_attempts=2,
            min_delay_seconds=0,
            retry_delay_seconds=0,
            glossary_path=glossary_path,
            system_prompt_path=system_prompt_path,
            fewshot_path=fewshot_path,
            show_progress=False,
            cache_file=cache_file,
            use_cache=True,
        )

        en_data = {"test": "Test value"}
        ru_data = {"test": "Тестовое значение"}

        en_path = temp_dir / "en.json"
        ru_path = temp_dir / "ru.json"
        dst_path = temp_dir / "es.json"

        en_path.write_text(json.dumps(en_data), encoding="utf-8")
        ru_path.write_text(json.dumps(ru_data, ensure_ascii=False), encoding="utf-8")

        # First run
        pipeline1 = TranslationPipeline(mock_client, config)
        pipeline1.run(en_path, ru_path, dst_path)

        # Verify cache file was created
        assert cache_file.exists()

        # Second run with new pipeline instance
        mock_client2 = MockLLMClient()
        pipeline2 = TranslationPipeline(mock_client2, config)
        pipeline2.run(en_path, ru_path, dst_path)

        # Should use cache, so no new API calls
        assert mock_client2._call_count == 0
