# optionally include .env files
# you can override variables in .env files
# mind that paths are caclucated from variables are
# relative to this Makefile location
-include ../.env .env ../Makefile.local Makefile.local

ifeq ($(shell uname -s),Darwin)
    REALPATH:=grealpath -em
else
    REALPATH:=realpath -em
endif
WORKDIR:=$(shell $(REALPATH) $(shell pwd))
# use PYBIN to customize python interpreter path
PYBIN:=$(shell which python3.11 || which python3 || which python)
VENV_DIR:=$(shell $(REALPATH) -em $(if $(VENV_DIR),$(VENV_DIR),$(WORKDIR)/../venv))

# make sure we use one specific shell
SHELL=/bin/bash
# .SHELLFLAGS=-e
VPY:=$(VENV_DIR)/bin/python
VPIP:=$(VENV_DIR)/bin/pip
VPIPC:=$(VENV_DIR)/bin/pip-compile
VFLAKE:=$(VENV_DIR)/bin/flake8
VBLACK:=$(VENV_DIR)/bin/black
VISORT:=$(VENV_DIR)/bin/isort
VBANDIT:=$(VENV_DIR)/bin/bandit
VDJANGO:=$(VENV_DIR)/bin/django-admin
VPYTEST:=$(VENV_DIR)/bin/pytest
VCOVERAGE:=$(VENV_DIR)/bin/coverage
VBASEROW:=$(VENV_DIR)/bin/baserow
VGUNICORN:=$(VENV_DIR)/bin/gunicorn

# will be used if no DJANGO_SETTINGS_MODULE is provided
DJANGO_SETTINGS_MODULE:=baserow.config.settings.dev
# ip:port to use when running dev server
RUNSERVER_BIND:=0.0.0.0:8000

VENV_TOUCH:=$(VENV_DIR)/bin/activate
DOCKER:=docker
DOCKERC:=docker compose

PYTEST_SPLITS:=1
PYTEST_SPLIT_GROUP:=1
PYTEST_EXTRA_ARGS?=

SOURCE_DIRS=./ ../premium/backend/ ../enterprise/backend/
BACKEND_SOURCE_DIRS=src/ ../premium/backend/src/ ../enterprise/backend/src/
BACKEND_TESTS_DIRS=tests/ ../premium/backend/tests/ ../enterprise/backend/tests/

BACKEND_TESTS_DIRS_FROM_ROOT=backend/tests/ premium/backend/tests/ enterprise/backend/tests/


#no-file targets
.PHONY: help venv venv-clean install-oss install install-extra package docker-build package-install\
	clean clean-all package-build package-clean deps deps-clean deps-install deps-install-dev deps-upgrade\
	lint lint-fix lint-python format sort make-translations compile-translations\
	test test-builder test-builder-parallel test-coverage test-parallel test-regenerate-ci-durations\
	ci-test-python ci-check-startup-python ci-coverage-report fix\
	run-dev


# This is a first target in the file, will be executed as default if no targets
# are specified. We'll use it to display usage
help:
	@echo "make commands available"
	@echo " make install - create a venv, install full Baserow package (base + premium/enterprise) in it"
	@echo "   make venv - create a venv"
	@echo "   make deps-install - install deps to venv"
	@echo " make install-oss - install Baserow OSS version without premium/enterprise"
	@echo " make install-extra - install Baserow premium/enterprise only (this still requires install-oss)"
	@echo " make lint - run lint/style tools"
	@echo " make lint-fix - run lint/style tools and fix the code"
	@echo " make package-build - build wheel package"
	@echo " make docker-build - build docker image for backend only"
	@echo " make clean - remove build artifacts"
	@echo " make clean-all - remove build artifacts and venv"
	@echo " make deps - update dependencies without upgrade"
	@echo "   make deps-upgrade - recalculate dependencies with versions upgrade"
	@echo " make deps-install - install runtime deps"
	@echo " make deps-install-dev - install development deps"
	@echo " make run-dev - run development server"


# touchfile for venv. If this file is present, the target won't be executed
# (so venv will be created from scratch only if there's no venv/bin/activate).
$(VENV_TOUCH):
	$(PYBIN) -m venv $(VENV_DIR)
	$(VPIP) install --upgrade pip==24.0
	touch $(VENV_TOUCH)

# this is a shortcut - use venv as a dependent target elsewhere
venv: $(VENV_TOUCH)

# install premium/enterprise apps
.install-extra:
	$(VPIP) install -e ../premium/backend/
	$(VPIP) install -e ../enterprise/backend/


# install base open-source version
.install-oss:
	$(VPIP) install -e .

# create venv and install base version of BR
install-oss: deps-install-dev .install-oss

install-extra: deps-install-dev .install-extra

# install premium/enterprise versions
install: deps-install-dev .install-oss .install-extra

# build wheel packages
package-build: venv deps-install-dev
	$(VPY) -m build . -o dist/
	$(VPY) -m build ../premium/backend/ -o dist/ || true
	$(VPY) -m build ../enterprise/backend/ -o dist/ || true


package-install: package
	for p in $(wildcard dist/*whl); do $(VPIP) install --force-reinstall dist/$${p}; done;

docker-build:
	$(DOCKER) build .

# rebuild deps for the app. do not upgrade already recorded deps
deps: venv install
	$(VPIPC) --no-upgrade requirements/base.in
	$(VPIPC) --no-upgrade requirements/dev.in

# rebuild and upgrade deps
deps-upgrade: venv install
	$(VPIPC) requirements/base.in
	$(VPIPC) requirements/dev.in

# install runtime deps
deps-install: venv
	# handle gracefull, as not all uses debian-alikes)
	(apt-get update && apt-get install -y libpq-dev postgresql-client) || true
	$(VPIP) install -r requirements/base.txt

# install dev deps
deps-install-dev: deps-install
	$(VPIP) install -r requirements/dev.txt

.check-dev:
	test -f $(VBASEROW) || $(MAKE) deps-install-dev install

# run lint check on backend code
lint: .check-dev
	$(VFLAKE) $(BACKEND_SOURCE_DIRS) $(BACKEND_TESTS_DIRS)
	$(VBLACK) $(BACKEND_SOURCE_DIRS) $(BACKEND_TESTS_DIRS)  --check --config=pyproject.toml
	$(VISORT) --check --skip generated $(BACKEND_SOURCE_DIRS) $(BACKEND_TESTS_DIRS)
	# TODO: make baserow command reading dotenv files
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS_MODULE) $(VBASEROW) makemigrations --dry-run --check
	$(VBANDIT) -r --exclude src/baserow/test_utils,src/baserow/config/settings/local.py $(BACKEND_SOURCE_DIRS)

lint-python: lint

format: .check-dev
	$(VBLACK) --config=pyproject.toml $(BACKEND_SOURCE_DIRS) $(BACKEND_TESTS_DIRS) || exit;

lint-fix: sort format

# compatibility with previous convention
fix: lint-fix

sort: .check-dev
	$(VISORT) --skip generated --overwrite-in-place $(BACKEND_SOURCE_DIRS) $(BACKEND_TESTS_DIRS) || exit;

test: .check-dev
	$(VPYTEST) $(BACKEND_TESTS_DIRS) || exit;

test-diff: .check-dev
	$(VPYTEST) $(BACKEND_TESTS_DIRS) --testmon || exit;

test-coverage: .check-dev
	$(VPYTEST) -n 10 --cov-report term --cov-report html:reports/html --cov=src $(BACKEND_TESTS_DIRS) || exit;

test-builder: .check-dev
	$(VPYTEST) tests/baserow/contrib/integrations tests/baserow/contrib/builder || exit

test-builder-parallel: .check-dev
	$(VPYTEST) tests/baserow/contrib/integrations tests/baserow/contrib/builder -n 10 || exit

test-automation: .check-dev
	$(VPYTEST) tests/baserow/contrib/integrations tests/baserow/contrib/automation || exit

test-automation-parallel: .check-dev
	$(VPYTEST) tests/baserow/contrib/integrations tests/baserow/contrib/automation -n 10 || exit

test-regenerate-ci-durations: .check-dev
	$(VPYTEST) $(BACKEND_TESTS_DIRS) --store-durations || exit;

test-parallel: .check-dev
	$(VPYTEST) $(BACKEND_TESTS_DIRS) -n 10 || exit;

test-diff-parallel: .check-dev
	$(VPYTEST) $(BACKEND_TESTS_DIRS) --testmon -n 10 || exit;

.make-django-cmd: .check-dev
	for pkg_dir in $(SOURCE_DIRS); do echo $$pkg_dir ; cd $$pkg_dir ; \
			$(VDJANGO) $(DJANGO_COMMAND) || true ; cd - ;\
	done

make-translations: DJANGO_COMMAND=makemessages -l en --ignore 'tests/*'
make-translations: .make-django-cmd


compile-translations: DJANGO_COMMAND=compilemessages -l en
compile-translations: .make-django-cmd


# coverage needs to be executed from repo root
# to match paths in backend/ premium/ and enterprise/
ci-test-python: .check-dev
	mkdir reports/ -p
	cd $(WORKDIR)/../ ; COVERAGE_FILE=backend/reports/.coverage.$(PYTEST_SPLIT_GROUP) $(VCOVERAGE) run \
	    --rcfile=backend/.coveragerc \
	    -m pytest -vv \
	    --durations-path=backend/.test_durations \
	    --splits $(PYTEST_SPLITS) \
	    --group $(PYTEST_SPLIT_GROUP) \
	    --junitxml=backend/reports/report.xml \
	    $(PYTEST_EXTRA_ARGS) $(BACKEND_TESTS_DIRS_FROM_ROOT);


# coverage needs to be executed from repo root
# to match paths in backend/ premium/ and enterprise/
ci-coverage-report: .check-dev
	cd $(WORKDIR)/../ ; cp backend/reports/.coverage.* . ; export COVERAGE_RCFILE=backend/.coveragerc  ; \
	$(VCOVERAGE) combine ; \
	$(VCOVERAGE) report ; \
	$(VCOVERAGE) xml -o coverage.xml


define check_startup_python
	@set -euo pipefail; set -x; \
	BASEROW_OSS_ONLY=$(1) DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS_MODULE) $(VDJANGO) check; \
	BASEROW_OSS_ONLY=$(1) DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS_MODULE) timeout --preserve-status 10s \
		$(VGUNICORN) --workers=1 -b 0.0.0.0:8002 \
		-k uvicorn.workers.UvicornWorker baserow.config.asgi:application
endef

ci-check-startup-python: .check-dev
	$(call check_startup_python,)

ci-check-startup-python-oss-only: .check-dev
	$(call check_startup_python,true)


# clean targets

# remove wheel packages from build output dir
package-clean:
	rm -fr dist/*


# remove venv
venv-clean:
	rm -fr $(VENV_DIR)

# clean env and build
clean: package-clean

clean-all: clean venv-clean

deps-clean:
	rm -f requirements/base.txt
	rm -f requirements/base.txt

run-dev: .check-dev
	$(VBASEROW) runserver $(RUNSERVER_BIND)
