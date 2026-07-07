CONDA_ENV  := pbpicat
ifdef NOCONDA
CONDA_RUN  :=
else
CONDA_RUN  := conda run -n $(CONDA_ENV) --no-capture-output
endif
SRC        := src
DOCS       := docs
LOCALE_DIR := src/pbpicat/locale
POT_FILE   := $(LOCALE_DIR)/pbpicat.pot
PO_LOCALES := en fr de es it ru vi zh_CN

# Python sources
PY_SOURCES := $(shell find $(SRC)/pbpicat -name "*.py" ! -path "*/__pycache__/*")

PO_FILES        := $(foreach lang,$(PO_LOCALES),$(LOCALE_DIR)/$(lang)/LC_MESSAGES/pbpicat.po)
TRANSLATE_STAMP := .translate.stamp

R  := \033[0m
B  := \033[1m
G  := \033[32m
Y  := \033[33m
C  := \033[36m

.DEFAULT_GOAL := help
.PHONY: all help venv venv-update install run test coverage lint format hooks \
        translate compile-mo force-translate new-lang docs docs-live dist srcdist clean

all: translate ## Build all generated artifacts (strings → .mo)

help: ## Show this help (default target)
	@printf "$(B)$(C)PBPicat — Development tasks$(R)\n\n"
	@printf "$(Y)Usage:$(R) make $(G)<target>$(R)\n\n"
	@printf "$(Y)Targets:$(R)\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS=":.*?## "}; {printf "  $(G)%-14s$(R) %s\n", $$1, $$2}'
	@printf "\n$(Y)Variables:$(R)\n"
	@printf "  $(G)NOCONDA$(R)        Bypass conda wrapping; tools must be in PATH\n"
	@printf "                 e.g. $(C)make test NOCONDA=1$(R)  or  $(C)export NOCONDA=1$(R)\n"

venv: ## Create the 'pbpicat' conda environment from environment.yml
	@printf "$(C)Creating conda environment '$(CONDA_ENV)'...$(R)\n"
	conda env create -f environment.yml
	@printf "$(G)Done! Activate with:$(R) conda activate $(CONDA_ENV)\n"

venv-update: ## Update the conda environment from environment.yml
	@printf "$(C)Updating conda environment '$(CONDA_ENV)'...$(R)\n"
	conda env update -f environment.yml --prune
	@printf "$(G)Done.$(R)\n"

install: ## Install the package in editable mode and register git hooks
	$(CONDA_RUN) pip install -e ".[dev]"
	$(CONDA_RUN) pre-commit install

run: ## Launch PBPicat (pass extra flags with ARGS="...")
	$(CONDA_RUN) python3 -m pbpicat $(ARGS)

test: ## Run the test suite
	$(CONDA_RUN) pytest

coverage: ## Run tests and open HTML coverage report
	$(CONDA_RUN) pytest --cov-report=term-missing --cov-report=html
	@printf "$(G)Report:$(R) $(Y)htmlcov/index.html$(R)\n"

lint: ## Check code style
	$(CONDA_RUN) ruff check $(SRC)
	$(CONDA_RUN) ruff format --check $(SRC)

format: ## Auto-format source code
	$(CONDA_RUN) ruff format $(SRC)
	$(CONDA_RUN) ruff check --fix $(SRC)

hooks: ## Run all pre-commit hooks on all files
	$(CONDA_RUN) pre-commit run --all-files

docs: ## Build HTML documentation
	$(CONDA_RUN) sphinx-build -b html $(DOCS) $(DOCS)/_build/html
	@printf "$(G)Open:$(R) $(DOCS)/_build/html/index.html\n"

docs-live: ## Build docs and watch for changes (hot reload)
	$(CONDA_RUN) sphinx-autobuild $(DOCS) $(DOCS)/_build/html

# ── i18n ──────────────────────────────────────────────────────────────────────

translate: $(TRANSLATE_STAMP) ## Extract translatable strings, update .po files and compile .mo

$(TRANSLATE_STAMP): $(PY_SOURCES) $(PO_FILES)
	@printf "$(C)Extracting from Python sources...$(R)\n"
	$(CONDA_RUN) pybabel extract -F babel.cfg --no-wrap --no-location \
	    --project=pbpicat \
	    --copyright-holder="Philippe Poilbarbe" \
	    --msgid-bugs-address="philippe@cardolan.net" \
	    -o $(POT_FILE) $(SRC)/pbpicat
	@printf "$(C)Updating .po files...$(R)\n"
	$(CONDA_RUN) pybabel update -i $(POT_FILE) -d $(LOCALE_DIR) -D pbpicat \
	    --no-fuzzy-matching --no-wrap
	$(CONDA_RUN) python tools/fix_po_files.py
	@printf "$(C)Compiling .mo files...$(R)\n"
	$(CONDA_RUN) pybabel compile -d $(LOCALE_DIR) -D pbpicat
	@printf "$(G)Done.$(R)\n"
	@touch $@

compile-mo: ## Compile .po → .mo without extracting strings
	$(CONDA_RUN) pybabel compile -d $(LOCALE_DIR) -D pbpicat

force-translate: ## Force-rebuild translations regardless of source changes
	@rm -f $(TRANSLATE_STAMP)
	@$(MAKE) translate

new-lang: ## Scaffold a new translation (usage: make new-lang LOCALE=de)
	@test -n "$(LOCALE)" || { \
	    printf "$(Y)Usage:$(R) make new-lang LOCALE=<lang-code>  (e.g. LOCALE=de)\n"; exit 1; }
	@test -f $(POT_FILE) || { \
	    printf "$(Y)Run 'make translate' first to generate the .pot template.$(R)\n"; exit 1; }
	$(CONDA_RUN) pybabel init -i $(POT_FILE) -d $(LOCALE_DIR) -D pbpicat \
	    -l $(LOCALE) --no-wrap
	@printf "\n$(G)Created:$(R) $(LOCALE_DIR)/$(LOCALE)/LC_MESSAGES/pbpicat.po\n\n"
	@printf "$(Y)Next steps:$(R)\n"
	@printf "  1. Edit the .po file and translate every msgstr entry.\n"
	@printf "  2. Set the $(B)language_name$(R) msgstr to the language's own name (e.g. 'Deutsch').\n"
	@printf "  3. Add $(B)$(LOCALE)$(R) to PO_LOCALES in the Makefile.\n"
	@printf "  4. Run: $(G)make translate$(R)\n"
	@printf "  5. Commit the .po and .mo files.\n"

# ── Distribution ──────────────────────────────────────────────────────────────

dist: translate ## Build a standalone executable for the current platform
	$(eval PBPICAT_VERSION := $(shell bash tools/git_version.sh))
	@printf "$(C)PyInstaller — version: $(PBPICAT_VERSION) — platform: $(shell $(CONDA_RUN) python3 -c 'import sys; print(sys.platform)')$(R)\n"
	$(CONDA_RUN) pip install -e . -q
	PBPICAT_VERSION=$(PBPICAT_VERSION) $(CONDA_RUN) pyinstaller --clean --noconfirm \
	    --distpath dist --workpath build/pyinstaller \
	    pbpicat.spec
	@printf "$(G)Done.$(R) Executable in $(Y)dist/$(R)\n"

srcdist: ## Build a source archive (git archive → dist/)
	$(eval PBPICAT_VERSION := $(shell bash tools/git_version.sh))
	@printf "$(C)Source archive — version: $(PBPICAT_VERSION)$(R)\n"
	@mkdir -p dist
	git archive --format=tar.gz \
	    --prefix=pbpicat-$(PBPICAT_VERSION)/ \
	    HEAD -o dist/pbpicat-$(PBPICAT_VERSION)-src.tar.gz
	@printf "$(G)Done.$(R) Archive in $(Y)dist/pbpicat-$(PBPICAT_VERSION)-src.tar.gz$(R)\n"

# ── Versioning ────────────────────────────────────────────────────────────────

bump-major: ## Bump MAJOR version (x.0.0)
	@$(CONDA_RUN) python3 tools/bump_version.py major

bump-minor: ## Bump MINOR version (x.y.0)
	@$(CONDA_RUN) python3 tools/bump_version.py minor

bump-patch: ## Bump PATCH version (x.y.z)
	@$(CONDA_RUN) python3 tools/bump_version.py patch

bump-set: ## Force a specific version (usage: make bump-set VERSION=x.y.z)
	@test -n "$(VERSION)" || { \
	    printf "$(Y)Usage:$(R) make bump-set VERSION=<x.y.z>\n"; exit 1; }
	@$(CONDA_RUN) python3 tools/bump_version.py set $(VERSION)

clean: ## Remove all build/cache artifacts
	rm -rf build dist *.egg-info .pytest_cache .coverage htmlcov $(DOCS)/_build
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -f $(POT_FILE) $(TRANSLATE_STAMP)
