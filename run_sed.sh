#!/bin/bash
sed -i 's/issues = validator.validate_file(test_file)/issues, _, _ = validator.validate_file(test_file)/g' tests/test_validator.py
sed -i 's/issues = validator.validate_file(test_file)/issues, _, _ = validator.validate_file(test_file)/g' tests/test_integration.py
