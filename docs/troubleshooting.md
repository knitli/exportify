<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Troubleshooting

Common issues and how to fix them.

> For command flags and options, see the [CLI Reference](cli-reference.md).
> For rule configuration, see the [Rule Engine reference](../src/exportify/rules/README.md).

## Symbols Not Being Exported

**Symptom**: A symbol you expect in `__all__` or `_dynamic_imports` is missing from generated output.

**Diagnosis**: Run with verbose output to see which rule (if any) matched the symbol:

```bash
exportify check --verbose
```

Common causes:

1. **No matching include rule.** The default rules cover `class`, `function`, `constant`, and `type_alias` member types. If your symbol doesn't match any `include` rule, it won't be exported. Add a rule for it:

   ```yaml
   - name: include-my-symbol
     priority: 750
     match:
       name_exact: MySpecialSymbol
     action: include
     propagate: parent
   ```

2. **An exclude rule is matching first.** If the symbol starts with `_`, the `exclude-private-members` rule (priority 900) will catch it before any include rule. Check for high-priority exclude rules that may be too broad.

3. **Wrong `member_type`.** The AST parser assigns each symbol a `member_type` (`class`, `function`, `constant`, `variable`, `type_alias`, `imported`). If a rule targets `member_type: class` but your symbol is detected as `variable`, the rule won't fire. Check the type by running `exportify check --verbose`.

4. **Module path pattern mismatch.** If your rule uses `module_pattern`, verify the pattern with a Python regex tester — `re.match()` anchors at the start but not the end, so `mypackage` matches `mypackage.core` too. Use `^mypackage$` for an exact match.

## Too Many Symbols Being Exported

**Symptom**: Symbols that should be internal appear in `__all__`.

**Diagnosis**: Check which rule is matching the unwanted symbol by running `exportify check --verbose`.

**Fix**: Add an exclude rule at a higher priority than the matching include rule:

```yaml
- name: exclude-internal-helpers
  priority: 850   # Higher than the 700-range include rules
  description: Exclude internal helper functions
  match:
    name_pattern: ^_?internal_.*
  action: exclude
```

Or use exact matching for specific symbols:

```yaml
- name: exclude-specific-symbol
  priority: 800
  match:
    name_exact: _InternalBase
  action: exclude
```

Remember: the first matching rule wins. If an exclude rule at priority 900 and an include rule at priority 700 both match, the exclude rule applies.

## Cache Seems Stale or Unexpected Results

**Symptom**: Running `exportify check` or `exportify sync` does not reflect recent changes to your source files, or produces results inconsistent with what you see in the files.

**Fix**: Clear the cache and re-run:

```bash
exportify cache clear
exportify check
```

The cache is keyed by file path and SHA-256 hash of the file contents. It should invalidate automatically when files change. If it does not, it may be corrupted.

Check cache statistics:

```bash
exportify cache stats
```

The cache is stored at `.exportify/cache/analysis_cache.json`. You can delete it manually if needed. Exportify will rebuild it on the next run.

See [Caching](caching.md) for details on how the cache works and its failure modes.

## `lateimport` Check Fails / Import Cannot Be Resolved

**Symptom**: `exportify check --lateimports` reports that a `lateimport()` call path is invalid.

The `--lateimports` check verifies that every `lateimport()` / `LateImport` call in your `_dynamic_imports` mapping resolves to an actual module in your package.

**Common causes**:

1. **Module was moved or renamed.** If you moved a module and ran `exportify sync`, the old `_dynamic_imports` entries may still point to the old path. Run `exportify sync` again to regenerate them.

2. **Typo in a manually written import.** Check the module path in your `__init__.py` against the actual file path.

3. **`lateimport` not in your dependencies.** The lateimports check is automatically skipped if `lateimport` is not listed as a project dependency. If you see the check running and failing unexpectedly, verify your `pyproject.toml` or `requirements.txt`.

**Note**: `exportify sync` does not modify `lateimport()` call paths directly — it regenerates `_dynamic_imports` from your rules. If the check still fails after running `sync`, the issue is in your source files, not the generated output.

## Generated File Overwrites Custom Code

**Symptom**: Running `exportify sync` removes custom imports, initialization code, or comments you added to `__init__.py`.

**Cause**: Exportify manages everything below the `# === MANAGED EXPORTS ===` sentinel. Anything you write below the sentinel will be overwritten.

**Fix**: Move your custom code above the sentinel:

```python
"""My package."""

from __future__ import annotations

# Custom code here — preserved across all exportify runs
__version__ = "1.0.0"
_registry: dict[str, type] = {}

def _init_registry() -> None:
    ...

_init_registry()

# === MANAGED EXPORTS ===

# Everything below this line is managed by exportify.
```

If a file has no `# === MANAGED EXPORTS ===` sentinel, exportify treats the entire file as user-managed and will not modify it. Add the sentinel yourself to opt in to management.

## Schema Version Error

**Symptom**: Exportify raises a `SchemaVersionError` when loading your config file.

**Possible error messages**:

```
SchemaVersionError: Missing schema_version in .exportify/config.yaml
Expected: 1.0
```

```
SchemaVersionError: Unsupported schema version 2.0 in .exportify/config.yaml
Supported versions: 1.0
Current version: 1.0
```

**Fix**:

1. Ensure your config file has `schema_version: "1.0"` at the top level.
2. If you have a config from an older version of exportify, run `exportify init --force` to regenerate it, then re-add your custom rules.
3. Run `exportify doctor` for a detailed diagnosis.

Currently supported schema versions: `"1.0"`.

## `__all__` Inconsistency Warnings

**Symptom**: `exportify check` reports that `__all__` in a module does not match the export rules.

**Fix**:

To sync everything at once:

```bash
exportify sync
```

To sync only `__all__` in regular modules (non-`__init__.py`):

```bash
exportify sync --module-all
```

To sync only `__init__.py` files:

```bash
exportify sync --package-all
```

Use `--dry-run` first to preview what would change:

```bash
exportify sync --dry-run
```

## Analysis Is Slow

**Symptom**: `exportify check` or `exportify sync` takes a long time on a large codebase.

**Expected behavior**: The first run after installation (or after `cache clear`) analyzes every file from scratch. Subsequent runs use cached results and should be fast.

Check cache statistics to confirm the cache is being used:

```bash
exportify cache stats
```


If the hit rate is low despite having run exportify before, the cache may be getting invalidated on every run. Possible causes:

- Files are being modified by a formatter or code generator between runs.
- The cache directory (`.exportify/cache/`) is being deleted by a clean script.
- A CI environment is not caching the `.exportify/` directory between runs.

The target hit rate is above 90% on incremental runs. See [Caching](caching.md) for the circuit breaker behavior and other failure modes.

---

## FAQ

### Can I use exportify in CI/CD?

Yes. `exportify check` exits non-zero on failures. Add `--strict` to also fail on warnings:

```bash
exportify check --strict
```

For machine-readable output (e.g., to parse results in a script):

```bash
exportify check --json
```

### Does this work with type checkers (mypy, pyright, ty)?

Yes. Generated files include `TYPE_CHECKING` blocks with proper type annotations so that static analysis tools see the exported names without incurring runtime import cost.

### Can I opt out of lazy loading?

The lazy loading pattern (`lateimport` + `__getattr__`) is what exportify generates by default. If you need standard eager imports instead, you can edit the preserved zone (above the sentinel) of your `__init__.py` to add direct imports, and configure exportify rules to exclude those symbols from the managed section so they aren't duplicated.

### Can I use this without `lateimport`?

Yes. The `lateimport` checks (`exportify check --lateimports`) are automatically skipped if `lateimport` is not listed in your project dependencies. The `sync` command uses the `lateimport`-based lazy loading pattern by default; if your project doesn't use `lateimport`, the generated files will still be syntactically valid but the `__getattr__` hook will reference an unavailable function. Add `lateimport` to your dependencies to use the full feature set, or customize your config to suppress generation of the lazy-load section.

### Does exportify modify my source files?

Exportify writes to:

- `__init__.py` files (the managed zone, below `# === MANAGED EXPORTS ===`)
- `__all__` declarations in regular modules when you run `exportify sync --module-all`

It never modifies any other source files.

### What Python versions are supported?

Python 3.12 and later.

### Where does exportify look for the config file?

In order:

1. `EXPORTIFY_CONFIG` environment variable (any path)
2. `.exportify/config.yaml`
3. `.exportify/config.yml`
4. `.exportify.yaml`
5. `.exportify.yml`
6. `exportify.yaml`
7. `exportify.yml`

If no config file is found, the rule engine starts with no rules and symbols are not exported by default.
