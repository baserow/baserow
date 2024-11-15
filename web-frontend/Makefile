ifeq ($(shell uname -s),Darwin)
    REALPATH:=grealpath -em
else
    REALPATH:=realpath -em
endif

WORKDIR:=$(shell $(REALPATH) $(shell pwd))

YARNBIN:=yarn
NODEBIN:=node
NPMBIN:=npm


.PHONY: clean clean-all package-build build install deps-install-dev deps-install eslint\
		stylelint format-scss lint lint-fix lint-javascript\
		jest test ci-test-javascript update-snapshots\
		deps deps-upgrade fix run-dev

help:
	@echo "web-frontend makefile. available targets:"
	@echo " make build - dummy build target"
	@echo " make install - install deps locally"
	@echo " make lint - run lint/style tools"
	@echo " make lint-fix - run lint/style tools and fix the code"
	@echo " make test - run tests"
	@echo " make clean - noop target"
	@echo " make run-dev - run development server"

clean:
	@echo 'nothing to clean yet'

clean-all: clean
	rm -fr node_modules/

build:
	@echo "this is just a dummy target. no build here yet."

package-build: build

deps-install:
	# install yarn if possible
	which yarn || $(NPMBIN) install -g yarn || true
	$(YARNBIN) install

install: deps-install

deps-install-dev:
	@echo "noop install"

eslint:
	$(YARNBIN) run eslint || exit;

stylelint:
	$(YARNBIN) run stylelint && $(YARNBIN) run prettier --check modules/**/*.scss || exit;

format-scss:
	$(YARNBIN) run prettier --write modules/**/*.scss || exit;


lint-fix:
	$(YARNBIN) run fix

# compatibility with previous convention
fix: lint-fix

lint: eslint stylelint

lint-javascript: lint

jest:
	$(YARNBIN) test || exit;

test: jest

ci-test-javascript:
	$(YARNBIN) test-coverage || exit;

update-snapshots:
	$(YARNBIN) run jest --updateSnapshot || exit;

deps:
	# noop

deps-upgrade:
	# noop

run-dev:
	$(YARNBIN) run dev


