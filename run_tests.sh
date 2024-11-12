#!/bin/bash

# Add both the project root and tests directory to Python path
export PYTHONPATH="$(pwd):$(pwd)/Tests:$PYTHONPATH"
export PIPENV_VERBOSITY=-1

# Run mamba tests
echo "Starting mamba tests..."
pipenv run mamba Tests/specs --enable-coverage

# Generate coverage reports in HTML format
pipenv run coverage html \
  --include="Alpha/*,CustomIndicators/*,Data/*,Execution/*,Initialization/*,Monitor/*,Order/*,PortfolioConstruction/*,Strategy/*,Tools/*" \
  --omit="Tests/*,*/__init__.py"

# Generate XML coverage only in CI environment
if [ "$CI" = "true" ]; then
  pipenv run coverage xml \
    --include="Alpha/*,CustomIndicators/*,Data/*,Execution/*,Initialization/*,Monitor/*,Order/*,PortfolioConstruction/*,Strategy/*,Tools/*" \
    --omit="Tests/*,*/__init__.py"
fi