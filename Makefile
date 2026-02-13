POETRY ?= poetry
RUN := $(POETRY) run
SRC := tools
DATA_EN := data/TTM_EN.json
DATA_RU := data/TTM_RU.json
DATA_DRAFT := data/TTM_RU_bad.json

# Configuration for translation commands
SOURCE_EN ?= $(DATA_EN)      # English source (required)
SOURCE_RU ?= $(DATA_RU)      # Russian reference (optional, enables dual-reference mode)
OUT_DST ?= data/TTM_ES.json  # Output file path
OUT_DRAFT ?= $(DATA_DRAFT)   # Draft/existing translation to use as hints
LOCALE ?= es                 # Target locale code
CACHE_FILE ?= .translation_cache.json  # Translation cache file

.PHONY: install format lint typecheck test check lint-i18n translate translate-ru \
        bootstrap-locale cache-stats clean help

help:
	@echo "Available targets:"
	@echo ""
	@echo "Development:"
	@echo "  install          - Install all dependencies including dev"
	@echo "  format           - Format code with ruff and fix imports"
	@echo "  lint             - Lint code with ruff"
	@echo "  typecheck        - Type check with mypy"
	@echo "  test             - Run all tests with pytest"
	@echo "  check            - Run lint, typecheck, test, and lint-i18n"
	@echo ""
	@echo "Translation:"
	@echo "  translate        - Translate to any language (auto-detects single/dual-reference)"
	@echo "  translate-ru     - Initial EN→RU translation (single-reference mode)"
	@echo "  lint-i18n        - Validate i18n key parity and placeholders"
	@echo "  bootstrap-locale - Generate glossary and few-shot for new locale"
	@echo ""
	@echo "Utilities:"
	@echo "  cache-stats      - Show translation cache statistics"
	@echo "  clean            - Remove caches and generated files"
	@echo ""
	@echo "Examples:"
	@echo "  make translate-ru                               - Initial EN→RU translation"
	@echo "  make translate LOCALE=ru SOURCE_RU=             - Same as above"
	@echo "  make translate LOCALE=es                        - EN+RU→ES translation"
	@echo "  make translate LOCALE=de OUT_DST=data/TTM_DE.json - Custom output path"
	@echo "  make bootstrap-locale LOCALE=fr TARGET_LANG=\"French\" - Generate glossary/fewshot"
	@echo "  make bootstrap-locale LOCALE=fr FORCE=1         - Regenerate existing files"

install:
	$(POETRY) install --with dev

format:
	$(RUN) ruff format $(SRC) tests
	$(RUN) ruff check --fix $(SRC) tests

lint:
	$(RUN) ruff check $(SRC) tests

typecheck:
	$(RUN) mypy $(SRC)

test:
	$(RUN) pytest

check: lint typecheck test lint-i18n

lint-i18n:
	$(RUN) python tools/lint_i18n.py --src $(SOURCE_EN) --dst $(OUT_DST)

translate:
	$(RUN) python tools/ttm_translate.py \
		--source-en $(SOURCE_EN) \
		$(if $(SOURCE_RU),--source-ru $(SOURCE_RU),--single-reference-mode) \
		--dst $(OUT_DST) \
		$(if $(OUT_DRAFT),--draft $(OUT_DRAFT),) \
		$(if $(LOCALE),--locale $(LOCALE),) \
		$(if $(CACHE_FILE),--cache-file $(CACHE_FILE),)

translate-ru:
	$(RUN) python tools/ttm_translate.py \
		--source-en $(SOURCE_EN) \
		--dst $(DATA_RU) \
		$(if $(OUT_DRAFT),--draft $(OUT_DRAFT),) \
		--locale ru \
		--single-reference-mode \
		$(if $(CACHE_FILE),--cache-file $(CACHE_FILE),)

bootstrap-locale:
	$(RUN) python tools/bootstrap_locale.py --locale $(LOCALE) $(if $(TARGET_LANG),--target-language "$(TARGET_LANG)",) $(if $(FORCE),--force,)

cache-stats:
	@if [ -f $(CACHE_FILE) ]; then \
		echo "Translation Cache Statistics:"; \
		echo "  File: $(CACHE_FILE)"; \
		echo "  Size: $$(du -h $(CACHE_FILE) | cut -f1)"; \
		echo "  Cached translations: $$(jq '.cache | length' $(CACHE_FILE) 2>/dev/null || echo 'N/A')"; \
		echo "  Model version: $$(jq -r '.version' $(CACHE_FILE) 2>/dev/null || echo 'N/A')"; \
	else \
		echo "Cache file not found: $(CACHE_FILE)"; \
	fi

clean:
	rm -rf .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -f $(CACHE_FILE)
