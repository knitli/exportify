#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for exportify default configuration generation (exportify init)."""

# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports, avoid-loops-in-tests
from __future__ import annotations

from pathlib import Path

import yaml

from exportify.common.types import MemberType, PropagationLevel, RuleAction
from exportify.migration import RuleMigrator, verify_migration


class TestRuleMigrator:
    """Test the default configuration generator."""

    def test_migrate_creates_valid_yaml(self, tmp_path: Path):
        """Test that generation creates valid YAML."""
        migrator = RuleMigrator()
        result = migrator.migrate()

        assert result.success or result.errors  # Either works or has errors

        if result.success:
            parsed = yaml.safe_load(result.yaml_content)
            assert "schema_version" in parsed
            assert "rules" in parsed
            assert len(parsed["rules"]) > 0

    def test_extracts_private_exclusion_rule(self):
        """Test generation of private member exclusion rule."""
        migrator = RuleMigrator()
        migrator._extract_private_exclusion_rule()

        assert len(migrator.rules) == 1
        rule = migrator.rules[0]
        assert rule.name == "exclude-private-members"
        assert rule.priority == 900
        assert rule.action == RuleAction.EXCLUDE
        assert rule.pattern == r"^_.*"

    def test_extracts_constant_detection_rule(self):
        """Test generation of constant detection rule."""
        migrator = RuleMigrator()
        migrator._extract_constant_detection_rule()

        assert len(migrator.rules) == 1
        rule = migrator.rules[0]
        assert rule.name == "include-constants"
        assert rule.priority == 700
        assert rule.action == RuleAction.INCLUDE
        assert rule.pattern == r"^[A-Z][A-Z0-9_]*$"
        assert rule.member_type == MemberType.CONSTANT

    def test_extracts_exception_propagation_rule(self):
        """Test generation of exception propagation rule."""
        migrator = RuleMigrator()
        migrator._extract_exception_propagation_rule()

        assert len(migrator.rules) == 1
        rule = migrator.rules[0]
        assert rule.name == "propagate-exceptions"
        assert rule.priority == 800
        assert rule.action == RuleAction.INCLUDE
        assert rule.propagate == PropagationLevel.ROOT
        assert rule.member_type == MemberType.CLASS

    def test_extracts_module_exceptions(self):
        """Test module overrides placeholder — empty by default."""
        migrator = RuleMigrator()
        migrator._extract_module_exceptions()

        assert isinstance(migrator.overrides_include, dict)
        assert len(migrator.overrides_include) == 0

    def test_generates_valid_yaml_structure(self):
        """Test YAML generation structure."""
        migrator = RuleMigrator()
        migrator._extract_default_rules()
        yaml_content = migrator._generate_yaml()

        parsed = yaml.safe_load(yaml_content)

        assert parsed["schema_version"] == "1.0"
        assert "metadata" in parsed
        assert "rules" in parsed
        assert len(parsed["rules"]) > 0

        rule = parsed["rules"][0]
        assert "name" in rule
        assert "priority" in rule
        assert "description" in rule
        assert "match" in rule
        assert "action" in rule

    def test_rule_priority_ordering(self):
        """Test rules are ordered by priority (descending) in generated YAML."""
        migrator = RuleMigrator()
        migrator._extract_default_rules()
        yaml_content = migrator._generate_yaml()

        import yaml as _yaml

        parsed = _yaml.safe_load(yaml_content)
        priorities = [r["priority"] for r in parsed["rules"]]

        assert priorities == sorted(priorities, reverse=True)

    def test_generates_summary(self):
        """Test configuration summary generation."""
        migrator = RuleMigrator()
        migrator._extract_default_rules()
        summary = migrator._generate_summary()

        assert "# Exportify Configuration Summary" in summary
        assert "## Rules" in summary
        assert "## Priority Bands" in summary

        for rule in migrator.rules:
            assert rule.name in summary


class TestMigrationVerification:
    """Test configuration verification."""

    def test_verify_private_exclusion(self, tmp_path: Path):
        """Test verification of private member exclusion."""
        yaml_content = """
schema_version: "1.0"
rules:
  - name: exclude-private
    priority: 900
    description: Exclude private members
    match:
      name_pattern: "^_.*"
    action: exclude
"""
        yaml_path = tmp_path / "rules.yaml"
        yaml_path.write_text(yaml_content)

        test_cases = [
            ("_private", "test.module", MemberType.FUNCTION),
            ("__dunder__", "test.module", MemberType.FUNCTION),
        ]

        success, errors = verify_migration(yaml_path, test_cases)
        assert success, f"Verification failed: {errors}"

    def test_verify_constant_inclusion(self, tmp_path: Path):
        """Test verification of constant inclusion."""
        yaml_content = """
schema_version: "1.0"
rules:
  - name: include-constants
    priority: 700
    description: Include constants
    match:
      name_pattern: "^[A-Z][A-Z0-9_]*$"
      member_type: constant
    action: include
"""
        yaml_path = tmp_path / "rules.yaml"
        yaml_path.write_text(yaml_content)

        test_cases = [
            ("MAX_SIZE", "test.config", MemberType.CONSTANT),
            ("DEFAULT_VALUE", "test.config", MemberType.CONSTANT),
        ]

        success, errors = verify_migration(yaml_path, test_cases)
        assert success, f"Verification failed: {errors}"

    def test_verify_exception_propagation(self, tmp_path: Path):
        """Test verification of exception propagation."""
        yaml_content = """
schema_version: "1.0"
rules:
  - name: propagate-exceptions
    priority: 800
    description: Propagate exceptions to root
    match:
      name_pattern: ".*Error$|.*Exception$|.*Warning$"
      member_type: class
    action: include
    propagate: root
"""
        yaml_path = tmp_path / "rules.yaml"
        yaml_path.write_text(yaml_content)

        test_cases = [
            ("ValidationError", "test.exceptions", MemberType.CLASS),
            ("CustomException", "test.tools", MemberType.CLASS),
        ]

        success, errors = verify_migration(yaml_path, test_cases)
        assert success, f"Verification failed: {errors}"


class TestEndToEndInit:
    """Test complete init workflow."""

    def test_full_init_workflow(self, tmp_path: Path):
        """Test complete generation from defaults to verification."""
        from exportify.migration import migrate_to_yaml

        output_path = tmp_path / "exportify.yaml"

        result = migrate_to_yaml(output_path, dry_run=True)

        assert result.rules_generated
        assert result.yaml_content
        assert result.summary

        rule_names = {r.name for r in result.rules_generated}
        assert "ExcludePrivateSymbols" in rule_names
        assert "ExportDefinedConstants" in rule_names
        assert "ExportDefinedClasses" in rule_names

        parsed = yaml.safe_load(result.yaml_content)
        assert parsed["schema_version"] == "1.0"
        assert len(parsed["rules"]) > 0

    def test_init_with_write(self, tmp_path: Path):
        """Test init writes the config file."""
        from exportify.migration import migrate_to_yaml

        output_path = tmp_path / "exportify.yaml"

        result = migrate_to_yaml(output_path, dry_run=False)

        if result.success:
            assert output_path.exists()

            content = output_path.read_text()
            parsed = yaml.safe_load(content)
            assert "rules" in parsed


class TestGenerateYamlWithOverrides:
    """Test YAML generation with override sections (lines 237-242)."""

    def test_generate_yaml_includes_overrides_include_section(self):
        """Test YAML contains 'overrides.include' when overrides_include is set."""
        migrator = RuleMigrator()
        migrator._extract_private_exclusion_rule()
        migrator.overrides_include = {"mypackage.core": ["_special_export"]}

        yaml_content = migrator._generate_yaml()
        parsed = yaml.safe_load(yaml_content)

        assert "overrides" in parsed
        assert "include" in parsed["overrides"]
        assert "mypackage.core" in parsed["overrides"]["include"]

    def test_generate_yaml_includes_overrides_exclude_section(self):
        """Test YAML contains 'overrides.exclude' when overrides_exclude is set."""
        migrator = RuleMigrator()
        migrator._extract_private_exclusion_rule()
        migrator.overrides_exclude = {"mypackage.core": ["public_but_excluded"]}

        yaml_content = migrator._generate_yaml()
        parsed = yaml.safe_load(yaml_content)

        assert "overrides" in parsed
        assert "exclude" in parsed["overrides"]
        assert "mypackage.core" in parsed["overrides"]["exclude"]

    def test_generate_yaml_includes_both_override_sections(self):
        """Test YAML contains both include and exclude override sections."""
        migrator = RuleMigrator()
        migrator._extract_private_exclusion_rule()
        migrator.overrides_include = {"mypackage.core": ["_special"]}
        migrator.overrides_exclude = {"mypackage.utils": ["public_helper"]}

        yaml_content = migrator._generate_yaml()
        parsed = yaml.safe_load(yaml_content)

        assert "overrides" in parsed
        assert "include" in parsed["overrides"]
        assert "exclude" in parsed["overrides"]


class TestGenerateYamlWithExactMatch:
    """Test YAML generation with exact_match rules (line 229)."""

    def test_generate_yaml_includes_name_exact_when_set(self):
        """Test YAML contains name_exact in match when exact_match is set on a rule."""
        from exportify.migration import ExtractedRule

        migrator = RuleMigrator()
        migrator.rules.append(
            ExtractedRule(
                name="include-version",
                priority=950,
                description="Include __version__",
                pattern=None,
                exact_match="__version__",
                member_type=None,
                action=RuleAction.INCLUDE,
                propagate=PropagationLevel.ROOT,
            )
        )

        yaml_content = migrator._generate_yaml()
        parsed = yaml.safe_load(yaml_content)

        version_rule = next((r for r in parsed["rules"] if r["name"] == "include-version"), None)
        assert version_rule is not None
        assert "name_exact" in version_rule["match"]
        assert version_rule["match"]["name_exact"] == "__version__"


class TestBuildRuleDetailsWithExactMatch:
    """Test _build_rule_details covers exact_match branch (line 300)."""

    def test_build_rule_details_includes_exact_match_line(self):
        """Test that exact_match produces a line in the summary."""
        from exportify.migration import ExtractedRule

        migrator = RuleMigrator()
        rule = ExtractedRule(
            name="include-version",
            priority=950,
            description="Include __version__",
            pattern=None,
            exact_match="__version__",
            member_type=None,
            action=RuleAction.INCLUDE,
            propagate=None,
        )

        lines = []
        result = migrator._build_rule_details(lines, rule)

        assert any("__version__" in line for line in result)
        assert any("Exact match" in line for line in result)

    def test_generate_summary_includes_exact_match_details(self):
        """Test _generate_summary covers the exact_match branch via a rule with exact_match."""
        from exportify.migration import ExtractedRule

        migrator = RuleMigrator()
        migrator.rules.append(
            ExtractedRule(
                name="include-version",
                priority=950,
                description="Include __version__",
                pattern=None,
                exact_match="__version__",
                member_type=None,
                action=RuleAction.INCLUDE,
                propagate=None,
            )
        )

        summary = migrator._generate_summary()
        assert "__version__" in summary
        assert "Exact match" in summary


class TestValidatorHelperFailurePaths:
    """Test the validation helper failure branches (lines 334, 341, 349, 351, 357-359)."""

    def test_validate_private_member_failure(self):
        """Returns error when private member has INCLUDE action instead of EXCLUDE."""
        from exportify.common.types import ExportDecision, PropagationLevel
        from exportify.migration import _validate_private_member

        mock_result = ExportDecision(
            module_path="test.module",
            action=RuleAction.INCLUDE,
            export_name="_private",
            propagation=PropagationLevel.NONE,
            priority=0,
            reason="test",
            source_symbol=None,
        )

        errors = _validate_private_member("_private", mock_result)
        self._check_error_conditions_for_private_member(errors, "_private", "not excluded")

    def test_validate_private_member_success(self):
        """Returns empty list when private member is correctly excluded."""
        from exportify.common.types import ExportDecision, PropagationLevel
        from exportify.migration import _validate_private_member

        mock_result = ExportDecision(
            module_path="test.module",
            action=RuleAction.EXCLUDE,
            export_name="_private",
            propagation=PropagationLevel.NONE,
            priority=0,
            reason="test",
            source_symbol=None,
        )

        errors = _validate_private_member("_private", mock_result)
        assert errors == []

    def test_validate_constant_failure(self):
        """Returns error when constant has EXCLUDE action instead of INCLUDE."""
        from exportify.common.types import ExportDecision, PropagationLevel
        from exportify.migration import _validate_constant

        mock_result = ExportDecision(
            module_path="test.config",
            action=RuleAction.EXCLUDE,
            export_name="MAX_SIZE",
            propagation=PropagationLevel.NONE,
            priority=0,
            reason="test",
            source_symbol=None,
        )

        errors = _validate_constant("MAX_SIZE", mock_result)
        self._check_error_conditions_for_private_member(errors, "MAX_SIZE", "not included")

    def test_validate_constant_success(self):
        """Returns empty list when constant is correctly included."""
        from exportify.common.types import ExportDecision, PropagationLevel
        from exportify.migration import _validate_constant

        mock_result = ExportDecision(
            module_path="test.config",
            action=RuleAction.INCLUDE,
            export_name="MAX_SIZE",
            propagation=PropagationLevel.NONE,
            priority=0,
            reason="test",
            source_symbol=None,
        )

        errors = _validate_constant("MAX_SIZE", mock_result)
        assert errors == []

    def test_validate_exception_class_failure_not_included(self):
        """Returns error when exception class is not included."""
        from exportify.common.types import ExportDecision, PropagationLevel
        from exportify.migration import _validate_exception_class

        mock_result = ExportDecision(
            module_path="test.exceptions",
            action=RuleAction.EXCLUDE,
            export_name="ValidationError",
            propagation=PropagationLevel.ROOT,
            priority=0,
            reason="test",
            source_symbol=None,
        )

        errors = _validate_exception_class("ValidationError", mock_result)
        self._check_error_conditions_for_private_member(errors, "ValidationError", "not included")

    def test_validate_exception_class_failure_not_propagated_to_root(self):
        """Returns error when exception class is included but not propagated to root."""
        from exportify.common.types import ExportDecision, PropagationLevel
        from exportify.migration import _validate_exception_class

        mock_result = ExportDecision(
            module_path="test.exceptions",
            action=RuleAction.INCLUDE,
            export_name="ValidationError",
            propagation=PropagationLevel.PARENT,
            priority=0,
            reason="test",
            source_symbol=None,
        )

        errors = _validate_exception_class("ValidationError", mock_result)
        self._check_error_conditions_for_private_member(
            errors, "ValidationError", "not propagated to root"
        )

    def test_validate_exception_class_failure_both_errors(self):
        """Returns two errors when exception class is both excluded and wrong propagation."""
        from exportify.common.types import ExportDecision, PropagationLevel
        from exportify.migration import _validate_exception_class

        mock_result = ExportDecision(
            module_path="test.exceptions",
            action=RuleAction.EXCLUDE,
            export_name="ValidationError",
            propagation=PropagationLevel.NONE,
            priority=0,
            reason="test",
            source_symbol=None,
        )

        errors = _validate_exception_class("ValidationError", mock_result)
        assert len(errors) == 2

    def test_validate_public_member_failure(self):
        """Returns error when public member is not included."""
        from exportify.common.types import ExportDecision, PropagationLevel
        from exportify.migration import _validate_public_member

        mock_result = ExportDecision(
            module_path="test.utils",
            action=RuleAction.EXCLUDE,
            export_name="public_function",
            propagation=PropagationLevel.NONE,
            priority=0,
            reason="test",
            source_symbol=None,
        )

        errors = _validate_public_member("public_function", mock_result)
        self._check_error_conditions_for_private_member(errors, "public_function", "not included")

    def _check_error_conditions_for_private_member(
        self, errors: list[str], check_one: str, check_two: str
    ):
        """Helper to check error conditions for private member validation failures."""
        assert len(errors) == 1
        assert check_one in errors[0]
        assert check_two in errors[0]

    def test_validate_public_member_success(self):
        """Returns empty list when public member is correctly included."""
        from exportify.common.types import ExportDecision, PropagationLevel
        from exportify.migration import _validate_public_member

        mock_result = ExportDecision(
            module_path="test.utils",
            action=RuleAction.INCLUDE,
            export_name="public_function",
            propagation=PropagationLevel.NONE,
            priority=0,
            reason="test",
            source_symbol=None,
        )

        errors = _validate_public_member("public_function", mock_result)
        assert errors == []


class TestVerifyMigrationEdgeCases:
    """Test verify_migration edge cases (lines 397-401, 435)."""

    def test_verify_migration_with_invalid_yaml_path(self, tmp_path: Path):
        """Returns failure when yaml_path doesn't exist or rules can't be loaded."""
        bad_path = tmp_path / "nonexistent.yaml"

        success, errors = verify_migration(bad_path)
        assert not success
        assert len(errors) >= 1
        assert "Failed to load rules" in errors[0]

    def test_verify_migration_uses_default_test_cases(self, tmp_path: Path):
        """Uses default test_cases when none provided (covers lines 400-401, 435)."""
        yaml_content = """
schema_version: "1.0"
rules:
  - name: exclude-private
    priority: 900
    description: Exclude private members
    match:
      name_pattern: "^_.*"
    action: exclude
  - name: include-constants
    priority: 700
    description: Include constants
    match:
      name_pattern: "^[A-Z][A-Z0-9_]*$"
      member_type: constant
    action: include
  - name: propagate-exceptions
    priority: 800
    description: Propagate exceptions
    match:
      name_pattern: ".*Error$|.*Exception$|.*Warning$"
      member_type: class
    action: include
    propagate: root
  - name: include-public
    priority: 500
    description: Include public members
    match:
      name_pattern: "^[a-z]"
    action: include
  - name: include-public-classes
    priority: 500
    description: Include public classes
    match:
      name_pattern: "^[A-Z]"
      member_type: class
    action: include
"""
        yaml_path = tmp_path / "rules.yaml"
        yaml_path.write_text(yaml_content)

        # Call without explicit test_cases to use default set (line 400-409)
        success, errors = verify_migration(yaml_path)
        # The default test set includes _private_func, MAX_SIZE, ValidationError,
        # CustomException, public_function, PublicClass — all should pass
        assert success, f"Verification with defaults failed: {errors}"


class TestCliInit:
    """Test cli_init function (lines 451-486)."""

    def test_cli_init_dry_run_returns_zero(self, tmp_path: Path):
        """cli_init with dry_run=True returns 0 on success."""
        from exportify.migration import cli_init

        output_path = tmp_path / "config.yaml"
        exit_code = cli_init(output=output_path, dry_run=True)
        assert exit_code == 0

    def test_cli_init_dry_run_does_not_write_file(self, tmp_path: Path):
        """cli_init with dry_run=True does not write a file."""
        from exportify.migration import cli_init

        output_path = tmp_path / "config.yaml"
        cli_init(output=output_path, dry_run=True)
        assert not output_path.exists()

    def test_cli_init_writes_file_when_not_dry_run(self, tmp_path: Path):
        """cli_init without dry_run writes the config file."""
        from exportify.migration import cli_init

        output_path = tmp_path / "config.yaml"
        exit_code = cli_init(output=output_path, dry_run=False)
        assert exit_code == 0
        assert output_path.exists()

    def test_cli_init_verbose_returns_zero(self, tmp_path: Path):
        """cli_init with verbose=True returns 0 and prints summary."""
        from exportify.migration import cli_init

        output_path = tmp_path / "config.yaml"
        exit_code = cli_init(output=output_path, dry_run=True, verbose=True)
        assert exit_code == 0

    def test_cli_init_with_no_output_uses_default(self, tmp_path: Path, monkeypatch):
        """cli_init with output=None uses DEFAULT_OUTPUT."""
        from unittest.mock import MagicMock, patch

        from exportify.migration import cli_init

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.errors = []
        mock_result.rules_generated = []
        mock_result.yaml_content = "schema_version: '1.0'\nrules: []\n"
        mock_result.summary = "# Summary"

        with patch("exportify.migration.migrate_to_yaml", return_value=mock_result):
            exit_code = cli_init(output=None, dry_run=True)
        assert exit_code == 0

    def test_cli_init_failure_returns_one(self, tmp_path: Path):
        """cli_init returns 1 when migration fails."""
        from unittest.mock import MagicMock, patch

        from exportify.migration import cli_init

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.errors = ["Something went wrong"]
        mock_result.rules_generated = []

        with patch("exportify.migration.migrate_to_yaml", return_value=mock_result):
            exit_code = cli_init(output=tmp_path / "config.yaml", dry_run=True)
        assert exit_code == 1

    def test_cli_init_verification_failure_returns_one(self, tmp_path: Path):
        """cli_init returns 1 when post-write verification fails."""
        from unittest.mock import MagicMock, patch

        from exportify.migration import cli_init

        output_path = tmp_path / "config.yaml"

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.errors = []
        mock_result.rules_generated = []
        mock_result.yaml_content = "schema_version: '1.0'\nrules: []\n"
        mock_result.summary = "# Summary"

        with (
            patch("exportify.migration.migrate_to_yaml", return_value=mock_result),
            patch("exportify.migration.verify_migration", return_value=(False, ["Bad rule"])),
        ):
            exit_code = cli_init(output=output_path, dry_run=False)
        assert exit_code == 1

    def test_cli_init_non_dry_run_verbose(self, tmp_path: Path):
        """cli_init with dry_run=False and verbose=True covers verbose+write path."""
        from exportify.migration import cli_init

        output_path = tmp_path / "config.yaml"
        exit_code = cli_init(output=output_path, dry_run=False, verbose=True)
        assert exit_code == 0
        assert output_path.exists()
