<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Export Rules Configuration

This directory contains YAML configuration files that define the rules for determining which Python symbols should be exported from `__init__.py` files using the lazy loading pattern.

## Overview

The exportify tool uses a **priority-based rule engine** to decide which symbols to export. Rules are evaluated in priority order (highest first), and the **first matching rule** determines the action.

## File Structure

```
rules/
├── README.md             # This file - documentation
└── default_rules.yaml    # Built-in rules (reference/template)
```

User rules are loaded from the project config file (`.exportify/config.yaml` by default). The config file uses the same YAML rule format as `default_rules.yaml`.

## Rule Schema

### Schema Version

All rule files must declare a schema version for compatibility:

```yaml
schema_version: "1.0"
```

**Supported versions**: `["1.0"]`

### Rule Structure

Each rule has the following structure:

```yaml
- name: "RuleName"           # Unique identifier (required)
  priority: 700              # 0-1000, higher = evaluated first (required)
  description: "What this rule does"  # Human-readable explanation (optional)
  match:                     # Match criteria (required)
    # ... matching conditions (see below)
  action: include            # include | exclude | no_decision (required)
  propagate: parent          # none | parent | root | custom (optional)
```

### Match Criteria

Match criteria specify when a rule applies. Multiple criteria can be combined:

#### Simple Matching

```yaml
match:
  name_exact: "SymbolName"           # Exact name match
  name_pattern: "^public_.*"         # Regex pattern
  module_exact: "mypackage.core"     # Exact module path
  module_pattern: ".*\\.types$"      # Regex pattern
  member_type: class                 # class | function | constant | variable | type_alias | imported | unknown
  provenance: imported               # defined_here | imported | alias_imported | unknown
```

**Important**: `name_pattern` and `module_pattern` use `re.match()`, which anchors at the start but not the end. Use `^` and `$` anchors explicitly to control matching boundaries.

#### Logical Combinations

```yaml
match:
  any_of:  # OR logic - at least one must match
    - name_pattern: ".*Error$"
    - name_pattern: ".*Exception$"

match:
  all_of:  # AND logic - all must match
    - member_type: class
    - module_pattern: ".*\\.core\\..*"
```

### Actions

- **`include`**: Export this symbol and propagate per `propagate` setting
- **`exclude`**: Do not export this symbol at all
- **`no_decision`**: Let lower-priority rules handle this (default fallback)

### Propagation Levels

When `action: include`, the `propagate` field controls how far up the package hierarchy the export travels:

- **`none`**: Export only in the defining module's `__init__.py`
- **`parent`**: Export in the parent module's `__init__.py`  *(default when `propagate` is omitted)*
- **`root`**: Propagate all the way to the package root
- **`custom`**: Reserved for future advanced use cases

**Example**: If `mypackage.core.types.models` defines `BasedModel`:
- `propagate: none` → Only in `mypackage/core/types/models/__init__.py`
- `propagate: parent` → In `mypackage/core/types/__init__.py`
- `propagate: root` → In `mypackage/__init__.py`

## Priority System

Rules are evaluated in priority order (highest first):

| Priority Range | Purpose | Examples |
|---------------|---------|----------|
| 1000 | Critical exclusions / special inclusions | Private symbols, `__version__` |
| 999 | Dunder exclusions | Dunder symbols |
| 900 | Infrastructure exclusions | lateimport components |
| 800 | Framework exclusions | Test fixtures, dev utilities |
| 700–702 | Defined symbols (exports) | Classes, functions, constants |
| 600 | Import handling | Aliased imports |
| 400 | Variable handling | Public variables |
| 300 | Propagation overrides | Root-level types, core utilities |
| 0 | Catch-all default | Fallback behavior |

**Note**: If multiple rules have the same priority, they are evaluated alphabetically by `name`.

## Default Rules

The `default_rules.yaml` file contains the standard rule set:

1. **IncludeDunderVersion** (1000): Always export `__version__` from root `__init__`
2. **ExcludePrivateSymbols** (1000): Skip `_private` symbols
3. **ExcludeDunderSymbols** (999): Skip `__dunder__` symbols (after `IncludeDunderVersion`)
4. **ExcludeLateImportComponents** (900): Prevent circular dependency on lateimport module
5. **ExcludeLateImportFunction** (900): Don't export the `lateimport` function itself
6. **ExcludeCreateLateGetattr** (900): Don't export the `create_late_getattr` infrastructure function
7. **ExcludeLateImportClass** (900): Don't export the `LateImport` infrastructure class
8. **ExcludeTestFixtures** (800): Skip pytest fixtures and test utilities
9. **ExcludeDevOnlyFunctions** (800): Skip `dev_*` prefixed functions
10. **ExportDefinedClasses** (700): Export defined classes, propagate to root
11. **ExportDefinedFunctions** (700): Export defined functions (including async), propagate to parent
12. **ExportDefinedConstants** (700): Export SCREAMING_SNAKE constants, propagate to parent
13. **ExportSpecialConstants** (702): Export constants from `constants.py` / `file_extensions.py` to root
14. **ExportTypeAliases** (700): Export type aliases, propagate to root
15. **ExportImportedSymbols** (600): Export aliased imports (`from x import y as z`), propagate to root
16. **ExportPublicVariables** (400): Exclude snake_case module-level variables
17. **CoreUtilsPropagateToRoot** (300): Core utilities (`core.utils`) propagate to package root
18. **SpecialUtilitiesPropagateToRoot** (300): Project-specific utility functions propagate to root
19. **EnsureINJECTEDPropagateToRoot** (300): `INJECTED` constant propagates to root
20. **PropagateToRoot** (300): Core types and exceptions propagate to package root
21. **DefaultNoDecision** (0): Fallback — no decision (symbol not exported)

## Overrides

Overrides provide **manual control** that bypasses all rules. Overrides are the **highest priority** (priority 9999 internally).

Overrides are set programmatically on the `RuleEngine` instance via `set_overrides()`, and are not part of the YAML rule file format. They are keyed by dotted module path:

```python
engine.set_overrides({
    "include": {
        "mypackage.internal": ["PublicHelper", "UtilityClass"]
    },
    "exclude": {
        "mypackage.core": ["_InternalBase"]
    }
})
```

**Include overrides**: Force export even if rules would exclude (propagates to ROOT by default)
**Exclude overrides**: Force exclusion even if rules would include

### When to Use Overrides

- **Special cases**: Symbols that need custom handling
- **Backward compatibility**: Keep deprecated exports without advertising them
- **Public API control**: Explicitly mark public vs internal symbols
- **Bug workarounds**: Temporary fixes while rules are refined

## Creating Custom Rules

Project-specific rules go in the config file (`.exportify/config.yaml` by default). Use the same YAML format as `default_rules.yaml`.

**Example** - Export all symbols with "Public" prefix:

```yaml
schema_version: "1.0"

rules:
  - name: "ExportPublicPrefix"
    priority: 750  # Between defined symbols (700) and imports (600)
    description: "Export symbols explicitly marked public"
    match:
      name_pattern: "^Public.*"
    action: include
    propagate: root  # Make available at package root
```

**Example** - Exclude experimental features:

```yaml
schema_version: "1.0"

rules:
  - name: "ExcludeExperimental"
    priority: 850  # High priority to override later rules
    description: "Skip experimental features"
    match:
      any_of:
        - name_pattern: "^experimental_.*"
        - module_pattern: ".*\\.experimental\\..*"
    action: exclude
```

**Example** - Export only aliased imports (likely re-exports):

```yaml
schema_version: "1.0"

rules:
  - name: "ExportAliasedImportsOnly"
    priority: 600
    description: "Export imports with aliases (likely intentional re-exports)"
    match:
      all_of:
        - member_type: imported
        - provenance: alias_imported
    action: include
    propagate: parent
```

## Member Types

The `member_type` criterion recognizes these symbol types:

| Member Type | Description | Example |
|------------|-------------|---------|
| `class` | Class definitions | `class Provider(Enum):` |
| `function` | Functions and async functions | `def get_provider():` |
| `constant` | SCREAMING_SNAKE_CASE variables | `MAX_SIZE = 1000` |
| `variable` | Module-level variables | `config = {}` |
| `type_alias` | Type aliases | `type StrDict = dict[str, str]` |
| `imported` | Imported symbols | `from x import y` |
| `unknown` | Member type could not be determined | Edge cases |

## Symbol Provenance

The `provenance` criterion distinguishes where symbols come from:

| Provenance | Description | Example |
|-----------|-------------|---------|
| `defined_here` | Defined in the current module | `class MyClass: ...` |
| `imported` | Regular imports | `from x import y` |
| `alias_imported` | Imports with aliases (likely re-exports) | `from x import y as z` |
| `unknown` | Provenance cannot be determined | Edge cases |

**Use cases**:
- Exclude all imported symbols: `provenance: imported`
- Only export aliased imports (likely re-exports): `provenance: alias_imported`
- Distinguish between defined and imported types: `provenance: defined_here`

## Regex Pattern Reference

Patterns use Python's `re` module syntax with `re.match()` (anchors at start, not end). Common patterns:

| Pattern | Matches | Example |
|---------|---------|---------|
| `^_.*` | Starts with underscore | `_private`, `__dunder` |
| `.*Error$` | Ends with "Error" | `ValueError`, `ImportError` |
| `^[A-Z_]+$` | All caps (constants) | `MAX_SIZE`, `API_KEY` |
| `.*\\.types$` | Module ending in "types" | `mypackage.core.types` |
| `.*\\.tests?\\..*` | Test modules | `mypackage.tests.unit` |

**Tip**: Use [regex101.com](https://regex101.com/) to test patterns with Python flavor.

## Validation

The rule engine validates rules when loaded:

**Schema validation**:
- `schema_version` must be present and supported
- All required fields must be present
- Actions must be valid (`include`, `exclude`, `no_decision`)
- Propagation levels must be valid (`none`, `parent`, `root`, `custom`)

**Pattern validation**:
- Regex patterns must compile successfully
- Invalid patterns raise `ValueError` with helpful messages

**Priority validation**:
- Priority must be 0-1000 inclusive
- Out-of-range priorities raise `ValueError`

## Loading Rules

Rules are loaded from the project config file. The config file search order is:

1. `EXPORTIFY_CONFIG` environment variable (any path)
2. `.exportify/config.yaml` in the current working directory
3. `.exportify/config.yml` in the current working directory
4. `.exportify.yaml` in the current working directory
5. `.exportify.yml` in the current working directory
6. `exportify.yaml` in the current working directory
7. `exportify.yml` in the current working directory

If no config file is found, the rule engine starts with no rules (symbols are not exported by default). The `default_rules.yaml` in this directory serves as a reference and template; it is not auto-loaded.

## Best Practices

### Rule Design

1. **Use descriptive names**: `ExportPublicAPI`, not `Rule1`
2. **Document intent**: Clear `description` fields help debugging
3. **Prefer specificity**: Narrow patterns over broad catches
4. **Test incrementally**: Add rules one at a time and verify behavior

### Priority Assignment

- **1000**: Only for absolute exclusions or must-include overrides (private, dunders, `__version__`)
- **900-800**: Framework/infrastructure exclusions
- **700**: Primary export rules
- **600**: Import handling
- **400-300**: Special cases and propagation overrides
- **0**: Default catch-all fallback

### Pattern Writing

- **Start simple**: Test with exact matches before adding patterns
- **Escape regex**: Use `\\.` for literal dots in module paths
- **Anchor patterns**: Use `^` and `$` to prevent partial matches (patterns use `re.match()`, which anchors at the start but not the end)
- **Test thoroughly**: Verify patterns match expected symbols only

### Overrides

- **Use sparingly**: Overrides bypass rule logic - prefer fixing rules
- **Document reasons**: Comment why each override exists
- **Plan deprecation**: Mark temporary overrides with TODO/FIXME
- **Keep organized**: Group by category (public API, deprecated, etc.)

## Troubleshooting

### Symbol not exported

1. Check if matching exclude rule (use `--verbose` with analyze command)
2. Check if member_type is recognized correctly
3. Verify module path matches expected pattern
4. Add override if rule fix is complex

### Symbol exported incorrectly

1. Check which rule matched (analysis output shows matched rule)
2. Verify priority order is correct
3. Add higher-priority exclusion rule if needed
4. Use override as temporary fix

### Pattern not matching

1. Test regex at regex101.com with Python flavor
2. Check for escaping issues (dots, brackets)
3. Remember `re.match()` anchors at start — use `$` to also anchor at end
4. Verify member_type and module_path are correct
5. Enable debug logging to see match attempts

## Examples

### Complete Rule Example

```yaml
schema_version: "1.0"

rules:
  # High-priority exclusion
  - name: "ExcludeInternalAPI"
    priority: 950
    description: "Hide internal implementation details"
    match:
      all_of:
        - module_pattern: ".*\\.internal\\..*"
        - member_type: function
    action: exclude

  # Standard export with parent propagation
  - name: "ExportProviderClasses"
    priority: 700
    description: "Export all provider implementations"
    match:
      all_of:
        - name_pattern: ".*Provider$"
        - member_type: class
    action: include
    propagate: parent

  # Root propagation for core types
  - name: "ExportCoreExceptions"
    priority: 300
    description: "Make exceptions available at package root"
    match:
      any_of:
        - name_pattern: ".*Error$"
        - name_pattern: ".*Exception$"
    action: include
    propagate: root
```

## Schema Evolution

When schema versions change, the rule engine handles migration automatically:

- **Backward compatible**: New versions support old configs
- **Automatic migration**: Configs upgraded during load
- **Deprecation warnings**: Old patterns get warnings before removal

**Current version**: `1.0`
**Supported versions**: `["1.0"]`

### Planned Enhancements (v1.1)

- **Docstring matching**: Match symbols based on docstring content or presence
- **Metadata matching**: Match on custom metadata fields
- **Conditional propagation**: Propagation level based on symbol characteristics

## Additional Resources

- **Main documentation**: `../README.md`
- **Type definitions**: `../common/types.py`
- **Rule engine**: `../export_manager/rules.py`

## Contributing

When adding new rules:

1. Understand existing rule priorities
2. Write clear, specific match criteria
3. Document the rule's purpose
4. Test with real codebase examples
5. Consider backward compatibility
6. Update this README if adding new patterns

---

**Version**: 1.0
**Last Updated**: 2026-02-23
**Schema Version**: 1.0
