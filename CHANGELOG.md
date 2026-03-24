## [unreleased]

### 🐛 Bug Fixes

- *(ci)* Ignore UP040 on sample_type_aliases.py
- Test failure in real project files type alias detection

### 🚜 Refactor

- Remove unused `nodes` argument from `_is_type_checking_block`

### ⚡ Performance

- Remove redundant file reads and optimize `validate_file` for metrics
- Optimize duplicate detection in __all__ exports

### 🧪 Testing

- Add logic tests for preserved function definitions in generator
- Fix ruff linting error in sample_type_aliases fixture
- Add test for invalid snapshot JSON manifest structure
- *(generator)* Add direct test for empty __all__ tuple generation
- *(generator)* Fix ruff error in sample_type_aliases.py
- Add test for annotated assignment to attribute target
- Add test for annotated assignment to attribute target

### ⚙️ Miscellaneous Tasks

- Optimization was already implemented on branch
- Fix linting error on test fixture
- Update project docs
## [0.2.6] - 2026-03-12

### 🧪 Testing

- Cover read_manifest error paths and fix type alias fixture

### ⚙️ Miscellaneous Tasks

- *(lint)* Lint/formatted codebase
## [0.2.4] - 2026-03-08

### 🐛 Bug Fixes

- Corrected a regression from last patch
## [0.2.3] - 2026-03-08

### 🐛 Bug Fixes

- Formatting errors and failure to detect empty or missing __init__ modules
## [0.2.2] - 2026-03-08

### 🐛 Bug Fixes

- *(src)* Fixed an issue where type aliases were not propagating correcting in __init__ modules and being discluded from _dynamic_imports. Added tests to improve handling of complex cases
## [0.2.1] - 2026-03-08

### 🚀 Features

- *(rules)* Improved default rules and consolidated with init-generated rules to simplify maintenance
## [0.2.0] - 2026-03-08

### 🐛 Bug Fixes

- *(docs)* Update docs to reflect new command structure and flags
- *(lints)* Linted, formatted, fixed codebase; updated tests; removed now dead code

### ⚙️ Miscellaneous Tasks

- *(licensing)* Reuse compliance
## [0.1.6] - 2026-03-07

### 🐛 Bug Fixes

- *(docs)* Missing readme field left pypi users in the dark
## [0.1.4] - 2026-03-07

### 🐛 Bug Fixes

- *(deconfliction)* Fixed an issue where two modules with the same rule priority were perceived as a conflict; now resolved alphabetically
## [0.1.3] - 2026-02-24

### 🐛 Bug Fixes

- Failing tests

### ⚙️ Miscellaneous Tasks

- *(lint)* Linted and fixed multiple files
## [0.1.2] - 2026-02-24

### 🚀 Features

- Add DEFAULT_SNAPSHOT_DIR constant to common config

### 🐛 Bug Fixes

- *(fix)* Corrected an issue with `fix` command where `from __future__ import annotations` would be inserted below other imports, causing syntax errors.

### ⚙️ Miscellaneous Tasks

- Ignore exportify snapshots dir and stray backup files
## [0.1.0] - 2026-02-23

### 🚀 Features

- Initial commit
- Enhance cache management with .gitignore support and error handling

### ⚙️ Miscellaneous Tasks

- *(license)* Re-establish reuse compliance
- Minor readme updates
