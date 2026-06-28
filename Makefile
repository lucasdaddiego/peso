# peso — spliced INDEC/BCRA series pipeline + static web app.
# Run `make` (or `make help`) to see what's available, grouped by stage.

PY         := uv run python
WEB        := web
NPM        := npm
PORT       := 5180
CF_PROJECT := peso

# Sub-makes (data, ci) are sequential; silence the "Entering directory" chatter.
MAKEFLAGS += --no-print-directory

.DEFAULT_GOAL := help
.PHONY: help setup \
        fetch splice validate data check \
        up build preview \
        fmt lint lint-py lint-web test test-py test-web ci \
        deploy clean

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\n\033[1mpeso\033[0m — make \033[36m<target>\033[0m\n"} \
		/^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0, 5); next} \
		/^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

##@ Setup
setup:  ## Install Python (uv) and web (npm) dependencies
	uv sync
	cd $(WEB) && $(NPM) install --ignore-scripts

##@ Data
fetch:  ## Download the source series into data/raw/ (datos.gob.ar + Bluelytics)
	$(PY) -m pipeline.fetch

splice:  ## Splice the series and write the JSON artifact (uses whatever is in data/raw/)
	$(PY) -m pipeline.build

validate:  ## Assert the artifact reproduces the official INDEC/BCRA figures
	$(PY) -m pipeline.validate

data:  ## Full rebuild: fetch → splice → validate
	@$(MAKE) fetch
	@$(MAKE) splice
	@$(MAKE) validate

check:  ## Verify the committed artifact reproduces a fresh rebuild (mirrors data.yml; re-fetches)
	git show HEAD:data/series.v1.json > /tmp/peso-committed-data.json
	git show HEAD:web/public/series.v1.json > /tmp/peso-committed-web.json
	@$(MAKE) data
	$(PY) -m pipeline.artifact_check /tmp/peso-committed-data.json data/series.v1.json
	$(PY) -m pipeline.artifact_check /tmp/peso-committed-web.json web/public/series.v1.json

##@ Develop
up:  ## Run the local dev server (http://localhost:$(PORT))
	cd $(WEB) && $(NPM) run dev -- --port $(PORT)

build:  ## Build the static site into web/dist
	cd $(WEB) && $(NPM) run build

preview: build  ## Serve the production build locally (http://localhost:$(PORT))
	cd $(WEB) && $(NPM) run preview -- --port $(PORT)

##@ Quality
fmt:  ## Auto-format + autofix the Python sources (ruff)
	uv run ruff format pipeline tests
	uv run ruff check --fix pipeline tests

lint-py:  ## Lint + format-check + typecheck the pipeline (ruff + mypy)
	uv run ruff check pipeline tests
	uv run ruff format --check pipeline tests
	uv run mypy

lint-web:  ## Typecheck the web app (tsc)
	cd $(WEB) && $(NPM) run typecheck

lint: lint-py lint-web  ## Lint + typecheck everything

test-py:  ## Python tests (100% statement+branch coverage gate)
	uv run pytest --cov=pipeline --cov-branch

test-web:  ## Web tests (100% coverage gate, vitest + jsdom)
	cd $(WEB) && $(NPM) run test:cov

test: test-py test-web  ## Run both test suites

ci:  ## Everything CI enforces, locally: lint → test → reproduce data
	@$(MAKE) lint
	@$(MAKE) test
	@$(MAKE) check

##@ Deploy
deploy: build  ## Deploy web/dist to Cloudflare Pages (needs wrangler auth)
	cd $(WEB) && wrangler pages deploy dist --project-name=$(CF_PROJECT)

clean:  ## Remove build artifacts, caches and downloaded raw data
	rm -rf $(WEB)/dist $(WEB)/.vite $(WEB)/coverage data/raw/*
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
