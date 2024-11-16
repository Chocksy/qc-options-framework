#!/bin/bash

# Add both the project root and tests directory to Python path
export PYTHONPATH="$(pwd):$(pwd)/Tests:$PYTHONPATH"
export PIPENV_VERBOSITY=-1

# Define coverage paths as arrays
INCLUDE_PATHS=(
    "Alpha/Base.py"
    "Alpha/Utils/*"
    "Monitor/Base.py"
    "Execution/Base.py"
    "Execution/Utils/*"
    "CustomIndicators/*"
    "Data/*"
    "Initialization/*"
    "Order/*"
    "PortfolioConstruction/*"
    "Strategy/*"
    "Tools/*"
)

OMIT_PATHS=(
    "Tests/*"
    "*/__init__.py"
    "Alpha/[!B]*.py"
    "Monitor/[!B]*.py"
    "Execution/[!B]*.py"
)

# Join arrays with commas
INCLUDE_STRING=$(IFS=,; echo "${INCLUDE_PATHS[*]}")
OMIT_STRING=$(IFS=,; echo "${OMIT_PATHS[*]}")

# Run mamba tests
echo "Starting mamba tests..."
if [ "$CI" = "true" ]; then
  pipenv run mamba Tests/specs --enable-coverage --format=junit > junit.xml
else
  pipenv run mamba Tests/specs --enable-coverage
fi

# Generate coverage reports in HTML format
pipenv run coverage html \
  --include="$INCLUDE_STRING" \
  --omit="$OMIT_STRING"

# Generate XML coverage only in CI environment
if [ "$CI" = "true" ]; then
  pipenv run coverage xml \
    --include="$INCLUDE_STRING" \
    --omit="$OMIT_STRING"
fi