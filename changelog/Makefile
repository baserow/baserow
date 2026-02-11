# 'realpath' command may be not available in Mac OS.
# In that case we use 'grealpath' from 'coreutils' package.
ifeq ($(shell uname -s),Darwin)
    REALPATH := grealpath -em
else
    REALPATH := realpath -em
endif

# Get the Python interpreter path
PYTHON:=$(shell which python3.14 || which python3 || which python)

# Get the directory of the current Makefile.
# If the Makefile is executed from another directory (e.g, using the '-C') flag
# $(WORKDIR) will contain the absolute path to the current Makefile directory,
# in this case '..../baserow/changelog/' (with the trailing '/')
WORKDIR := $(dir $($(REALPATH) $(lastword $(MAKEFILE_LIST))))
ARGS := $(filter-out $(firstword $(MAKECMDGOALS)),$(MAKECMDGOALS))
REQUIREMENTS := $(WORKDIR)requirements.txt
VENV := $(WORKDIR)venv
PIP := $(VENV)/bin/python -m pip

# Executables
CHANGELOG := $(VENV)/bin/python $(WORKDIR)src/changelog.py
BANDIT := $(VENV)/bin/bandit
BLACK := $(VENV)/bin/black
FLAKE8 := $(VENV)/bin/flake8
ISORT := $(VENV)/bin/isort
PYTEST := $(VENV)/bin/pytest

# Display the help message.
# If no targets are specified this will be executed by default.
help:
	@echo "make commands available"
	@echo " add         add a new changelog entry"
	@echo " release     add a new release. Usage: 'make release -- 1.2.3'"
	@echo " purge       delete all changelog entries"
	@echo " generate    generate a new 'changelog.md' file without making a new release"
	@echo ""
	@echo " lint        run lint/style tools"
	@echo " format      run black to reformat the code"
	@echo " sort        sort the imports"
	@echo " test        run the test suite"
	@echo ""
	@echo " clean       remove Python virtual environment directory"

# Create a new Python virtual environment and install the dependencies.
# When finished, the 'touch' command updates the modified date of the 'VENV'
# folder, avoiding unneeded rebuilds
$(VENV) $(PIP): $(PYTHON) $(REQUIREMENTS)
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -r $(REQUIREMENTS)
	$(PIP) install .
	touch $(VENV)

$(BANDIT) $(BLACK) $(FLAKE8) $(ISORT) $(PYTEST): $(VENV)

# Add a new changelog entry
.PHONY: add
add: $(VENV)
	$(CHANGELOG) add $(ARGS)

# Add a new release
.PHONY: release
release: $(VENV)
	$(CHANGELOG) release $(ARGS)

# Delete all changelog entries
.PHONY: purge
purge: $(VENV)
	$(CHANGELOG) purge $(ARGS)

# Generate a new 'changelog.md' file
.PHONY: generate
generate: $(VENV)
	$(CHANGELOG) generate $(ARGS)

# Check the code for linting errors
.PHONY: lint
lint: $(BANDIT) $(BLACK) $(FLAKE8) $(ISORT)
	$(FLAKE8) src tests
	$(BLACK) . --extend-exclude='/generated/' --check
	$(ISORT) --check --skip generated --profile black src tests
	$(BANDIT) -r src

# Reformat the code according to black style
.PHONY: format
format: $(BLACK)
	$(BLACK) . || exit;

# Sort the Python import statements
.PHONY: sort
sort: $(ISORT)
	$(ISORT) --skip generated --profile black src tests || exit;

# Run the test suite
.PHONY: test
test: $(PYTEST)
	$(PYTEST) tests || exit;

# Remove the virtual environment directory
.PHONY: clean
clean:
	-rm -r $(VENV)

# Prevent make from interpreting the arguments as targets
%:
	@:
