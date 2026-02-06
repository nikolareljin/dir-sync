APP_NAME ?= dir-sync
VERSION ?= $(shell cat VERSION 2>/dev/null || echo 0.1.0)
PREFIX ?= $(HOME)/.local
DESTDIR ?=

REPO_ROOT := $(CURDIR)
HELPERS_DIR := scripts/script-helpers
HELPERS_SCRIPTS := $(HELPERS_DIR)/scripts
PYTHON ?= python3

REPO_SLUG ?= nikolareljin/dir-sync
PPA ?=
PPA_KEY_ID ?=
PPA_SERIES ?= jammy
BREW_HOMEPAGE ?= https://github.com/$(REPO_SLUG)
BREW_TAP_REPO ?=
BREW_TAP_BRANCH ?= main
BREW_TARBALL_URL ?= https://github.com/$(REPO_SLUG)/releases/download/v$(VERSION)/$(APP_NAME)-$(VERSION).tar.gz

.DEFAULT_GOAL := help

.PHONY: help check-submodule update lint test ci run clean build install uninstall \
	package-init package-refresh deb rpm ppa ppa-dry brew brew-formula brew-publish \
	package-all

help:
	@echo "Dir Sync Make targets"
	@echo ""
	@echo "Core:"
	@echo "  make update           Update git submodules"
	@echo "  make lint             Run lint checks"
	@echo "  make test             Run unit tests"
	@echo "  make ci               Run lint + tests"
	@echo "  make build            Build dist/dir-sync with PyInstaller"
	@echo "  make run              Run app from source"
	@echo "  make install          Install built binary to \$$DESTDIR\$$PREFIX/bin/$(APP_NAME)"
	@echo "  make uninstall        Remove installed binary from \$$DESTDIR\$$PREFIX/bin/$(APP_NAME)"
	@echo ""
	@echo "Packaging:"
	@echo "  make package-init     Initialize packaging metadata/templates"
	@echo "  make package-refresh  Re-render packaging templates from packaging.env"
	@echo "  make deb              Build Debian artifacts"
	@echo "  make rpm              Build RPM artifacts"
	@echo "  make ppa-dry-run      Build signed source package for PPA (no upload)"
	@echo "  make ppa              Upload source package to Launchpad PPA"
	@echo "  make brew             Build Homebrew tarball + formula"
	@echo "  make brew-publish     Publish formula to Homebrew tap"
	@echo "  make package-all      Build deb + rpm + brew outputs"
	@echo ""
	@echo "Variables:"
	@echo "  VERSION=$(VERSION)"
	@echo "  PREFIX=$(PREFIX)"
	@echo "  REPO_SLUG=$(REPO_SLUG)"
	@echo "  PPA=ppa:owner/name PPA_KEY_ID=<gpg-key> [PPA_SERIES=$(PPA_SERIES)]"
	@echo "  BREW_TAP_REPO=owner/homebrew-tap [BREW_TAP_BRANCH=$(BREW_TAP_BRANCH)]"

check-submodule:
	@test -f "$(HELPERS_DIR)/helpers.sh" || { \
		echo "Missing submodule: script-helpers"; \
		echo "Run ./scripts/update.sh to set it up first."; \
		exit 1; \
	}

update:
	./scripts/update.sh

lint: check-submodule
	./scripts/lint.sh

test: check-submodule
	./scripts/run_tests.sh

ci: lint test

run:
	$(PYTHON) -m dirsync.app

clean:
	rm -rf build dist *.spec

build: check-submodule
	./scripts/build.sh

install: build
	install -d "$(DESTDIR)$(PREFIX)/bin"
	install -m 0755 "dist/$(APP_NAME)" "$(DESTDIR)$(PREFIX)/bin/$(APP_NAME)"

uninstall:
	rm -f "$(DESTDIR)$(PREFIX)/bin/$(APP_NAME)"

package-init: check-submodule
	bash "$(HELPERS_SCRIPTS)/packaging_init.sh" --repo "$(REPO_ROOT)"

package-refresh: check-submodule
	bash "$(HELPERS_SCRIPTS)/packaging_init.sh" --repo "$(REPO_ROOT)" --force

deb: check-submodule package-init
	bash "$(HELPERS_SCRIPTS)/build_deb_artifacts.sh" --repo "$(REPO_ROOT)" --prebuild "true"

rpm: check-submodule package-init
	bash "$(HELPERS_SCRIPTS)/build_rpm_artifacts.sh" --repo "$(REPO_ROOT)" --prebuild "make build"

ppa-dry-run: check-submodule package-init
	@if [ -z "$(PPA)" ] || [ -z "$(PPA_KEY_ID)" ]; then \
		echo "Set PPA and PPA_KEY_ID. Example:"; \
		echo "make ppa-dry-run PPA=ppa:owner/name PPA_KEY_ID=ABC123"; \
		exit 2; \
	fi
	bash "$(HELPERS_SCRIPTS)/ppa_upload.sh" \
		--repo "$(REPO_ROOT)" \
		--ppa "$(PPA)" \
		--key-id "$(PPA_KEY_ID)" \
		--series "$(PPA_SERIES)" \
		--prebuild "true" \
		--dry-run

ppa: check-submodule package-init
	@if [ -z "$(PPA)" ] || [ -z "$(PPA_KEY_ID)" ]; then \
		echo "Set PPA and PPA_KEY_ID. Example:"; \
		echo "make ppa PPA=ppa:owner/name PPA_KEY_ID=ABC123"; \
		exit 2; \
	fi
	bash "$(HELPERS_SCRIPTS)/ppa_upload.sh" \
		--repo "$(REPO_ROOT)" \
		--ppa "$(PPA)" \
		--key-id "$(PPA_KEY_ID)" \
		--series "$(PPA_SERIES)" \
		--prebuild "true"

brew: check-submodule package-init
	bash "$(HELPERS_SCRIPTS)/build_brew_tarball.sh" \
		--name "$(APP_NAME)" \
		--repo "$(REPO_ROOT)" \
		--version-file "$(REPO_ROOT)/VERSION" \
		--exclude ".git" \
		--exclude ".venv" \
		--exclude "dist" \
		--exclude "build" \
		--exclude "__pycache__"
	bash "$(HELPERS_SCRIPTS)/gen_brew_formula.sh" \
		--name "$(APP_NAME)" \
		--desc "Cross-platform rsync directory synchronizer" \
		--homepage "$(BREW_HOMEPAGE)" \
		--tarball "$(REPO_ROOT)/dist/$(APP_NAME)-$(VERSION).tar.gz" \
		--url "$(BREW_TARBALL_URL)" \
		--version "$(VERSION)" \
		--license "MIT" \
		--entrypoint "$(APP_NAME)" \
		--formula-path "$(REPO_ROOT)/packaging/brew/$(APP_NAME).rb"

brew-formula: brew

brew-publish: check-submodule brew
	@if [ -z "$(BREW_TAP_REPO)" ]; then \
		echo "Set BREW_TAP_REPO=owner/homebrew-tap"; \
		exit 2; \
	fi
	HOMEBREW_TAP_REPO="$(BREW_TAP_REPO)" \
	HOMEBREW_TAP_BRANCH="$(BREW_TAP_BRANCH)" \
	bash "$(HELPERS_SCRIPTS)/publish_homebrew.sh" \
		--repo "$(REPO_ROOT)" \
		--formula "$(REPO_ROOT)/packaging/brew/$(APP_NAME).rb" \
		--name "$(APP_NAME)"

package-all: deb rpm brew
