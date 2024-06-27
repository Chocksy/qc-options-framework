#!/bin/bash

# Add both the project root and tests directory to Python path
export PYTHONPATH="$(pwd):$(pwd)/Tests:$PYTHONPATH"
# Run mamba tests
echo "Starting mamba tests..."
pipenv run mamba Tests/specs --enable-coverage

# Generate coverage report
pipenv run coverage html