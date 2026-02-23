<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Init / Migration Tool Documentation

## Overview

The `init` command (and the underlying `migrate_to_yaml()` function) generates a starter
`.exportify/config.yaml` with sensible default rules, suitable for most Python packages.

This is used when setting up exportify for the first time. It is not a "migration" from
another system — it simply creates a well-structured default configuration that can then
be customised.

## CLI Usage

```bash
# Create .exportify/config.yaml in the current directory
exportify init

# Preview generated config without writing files
exportify init --dry-run

# Write to a custom location
exportify init --output path/to/rules.yaml

# Overwrite an existing config file
exportify init --force

# Show a full configuration summary
exportify init --verbose
```

## Default Output Location

By default the config is written to:

```
.exportify/config.yaml
```

## Generated Rules

`exportify init` produces a YAML file with the following built-in rules:

| Rule | Priority | Description |
|------|----------|-------------|
| `exclude-private-members` | 900 | Exclude names starting with `_` |
| `propagate-exceptions` | 800 | Propagate `*Error`/`*Exception`/`*Warning` classes to root |
| `include-constants` | 700 | Include SCREAMING_SNAKE_CASE constants |
| `include-type-aliases` | 650 | Include type aliases |
| `include-public-functions` | 500 | Include public functions |
| `include-public-classes` | 500 | Include public classes (CamelCase) |

Example snippet of the generated YAML:

```yaml
schema_version: "1.0"

rules:
  - name: exclude-private-members
    priority: 900
    description: Exclude private members (starting with underscore)
    match:
      name_pattern: ^_.*
    action: exclude

  - name: propagate-exceptions
    priority: 800
    description: Propagate exception classes to root package
    match:
      name_pattern: .*Error$|.*Exception$|.*Warning$
      member_type: class
    action: include
    propagate: root
```

## Python API

### `migrate_to_yaml()`

```python
from pathlib import Path
from exportify.migration import migrate_to_yaml

result = migrate_to_yaml(
    output_path=Path(".exportify/config.yaml"),
    dry_run=True  # Don't write files
)

print(result.yaml_content)
print(f"Rules generated: {len(result.rules_generated)}")
```

**Signature**:

```python
def migrate_to_yaml(
    output_path: Path = DEFAULT_OUTPUT,
    *,
    dry_run: bool = False,
) -> MigrationResult:
    ...
```

`DEFAULT_OUTPUT` is `Path.cwd() / ".exportify" / "config.yaml"`.

**`MigrationResult` fields**:

```python
@dataclass
class MigrationResult:
    yaml_content: str
    rules_generated: list[ExtractedRule]
    overrides_generated: dict[str, dict[str, list[str]]]
    summary: str
    success: bool
    errors: list[str]
```

### `verify_migration()`

Verifies that a generated config produces the expected behaviour for common symbol
patterns.

```python
from pathlib import Path
from exportify.migration import verify_migration

success, errors = verify_migration(
    yaml_path=Path(".exportify/config.yaml")
)

if success:
    print("Config verified - behaviour is correct")
else:
    for error in errors:
        print(f"  {error}")
```

Custom test cases can also be provided:

```python
from exportify.common.types import MemberType

test_cases = [
    ("_private", "mypackage.core", MemberType.FUNCTION),   # Should exclude
    ("MAX_SIZE", "mypackage.config", MemberType.CONSTANT),  # Should include
    ("CustomError", "mypackage.exc", MemberType.CLASS),     # Should propagate
]

success, errors = verify_migration(
    yaml_path=Path(".exportify/config.yaml"),
    test_cases=test_cases,
)
```

## Next Steps After Init

1. **Review the generated YAML**: Check `.exportify/config.yaml`
2. **Run verification**: `exportify check --source src/yourpackage`
3. **Customise rules**: Add project-specific rules as needed
4. **Generate exports**: `exportify generate --source src/yourpackage`

## Architecture

The init workflow is implemented in `src/exportify/migration.py`:

- **`RuleMigrator`**: Builds the default rule set
  - `_extract_default_rules()`: Adds the 6 standard rules
  - `_extract_module_exceptions()`: Placeholder for project-specific overrides
  - `_generate_yaml()`: Serialises rules to YAML
  - `_generate_summary()`: Produces a human-readable summary

- **`migrate_to_yaml()`**: Entry point used by both the CLI and the Python API
- **`verify_migration()`**: Validates that a config file matches expected rule behaviour
