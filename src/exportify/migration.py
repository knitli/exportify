# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: no-relative-imports
# ruff: noqa: RUF001
"""Default configuration generator for exportify.

This module generates a starter `.exportify.yaml` with sensible default rules,
suitable for most Python packages.

Workflow:
    1. Build a default rule set (private exclusion, public members, exceptions, etc.)
    2. Serialize to YAML
    3. Optionally write to disk
    4. Validate the generated config

Usage:
    exportify init [--output PATH] [--dry-run]
"""

from __future__ import annotations

import re

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from exportify.common.types import MemberType, PropagationLevel, RuleAction


DEFAULT_OUTPUT = Path.cwd() / ".exportify" / "config.yaml"
SCHEMA_VERSION = "1.0"


@dataclass
class ExtractedRule:
    """A rule that will appear in the generated configuration."""

    name: str
    priority: int
    description: str
    pattern: str | None
    exact_match: str | None
    member_type: MemberType | None
    action: RuleAction
    propagate: PropagationLevel | None
    source_line: int | None = None


@dataclass
class MigrationResult:
    """Result of the configuration-generation process."""

    yaml_content: str
    rules_generated: list[ExtractedRule]
    overrides_generated: dict[str, dict[str, list[str]]]
    summary: str
    success: bool
    errors: list[str]


class RuleMigrator:
    """Generates a default exportify YAML configuration."""

    def __init__(self) -> None:
        """Initialize with empty state."""
        self.rules: list[ExtractedRule] = []
        self.overrides_include: dict[str, list[str]] = {}
        self.overrides_exclude: dict[str, list[str]] = {}
        self.errors: list[str] = []

    def migrate(self) -> MigrationResult:
        """Generate a default exportify configuration.

        Returns:
            MigrationResult with YAML content and generation details.
        """
        self._extract_default_rules()
        self._extract_module_exceptions()

        yaml_content = self._generate_yaml()
        summary = self._generate_summary()

        return MigrationResult(
            yaml_content=yaml_content,
            rules_generated=self.rules,
            overrides_generated={
                "include": self.overrides_include,
                "exclude": self.overrides_exclude,
            },
            summary=summary,
            success=len(self.errors) == 0,
            errors=self.errors,
        )

    def _extract_default_rules(self) -> None:
        """Build the default set of exportify rules."""
        self._extract_private_exclusion_rule()
        self._extract_constant_detection_rule()
        self._extract_exception_propagation_rule()
        self._extract_type_alias_rule()
        self._extract_function_class_inclusion_rule()

    def _extract_private_exclusion_rule(self) -> None:
        """Exclude private members (starting with underscore)."""
        self.rules.append(
            ExtractedRule(
                name="exclude-private-members",
                priority=900,
                description="Exclude private members (starting with underscore)",
                pattern=r"^_.*",
                exact_match=None,
                member_type=None,
                action=RuleAction.EXCLUDE,
                propagate=None,
                source_line=None,
            )
        )

    def _extract_constant_detection_rule(self) -> None:
        """Include module-level constants (SCREAMING_SNAKE_CASE)."""
        self.rules.append(
            ExtractedRule(
                name="include-constants",
                priority=700,
                description="Include module-level constants (SCREAMING_SNAKE_CASE)",
                pattern=r"^[A-Z][A-Z0-9_]*$",
                exact_match=None,
                member_type=MemberType.CONSTANT,
                action=RuleAction.INCLUDE,
                propagate=PropagationLevel.NONE,
                source_line=None,
            )
        )

    def _extract_exception_propagation_rule(self) -> None:
        """Propagate exception classes to the root package."""
        self.rules.append(
            ExtractedRule(
                name="propagate-exceptions",
                priority=800,
                description="Propagate exception classes to root package",
                pattern=r".*Error$|.*Exception$|.*Warning$",
                exact_match=None,
                member_type=MemberType.CLASS,
                action=RuleAction.INCLUDE,
                propagate=PropagationLevel.ROOT,
                source_line=None,
            )
        )

    def _extract_type_alias_rule(self) -> None:
        """Include type aliases."""
        self.rules.append(
            ExtractedRule(
                name="include-type-aliases",
                priority=650,
                description="Include type aliases (detected via TypeAlias or capital name)",
                pattern=r"^[A-Z][a-zA-Z0-9]*$",
                exact_match=None,
                member_type=MemberType.TYPE_ALIAS,
                action=RuleAction.INCLUDE,
                propagate=PropagationLevel.PARENT,
                source_line=None,
            )
        )

    def _extract_function_class_inclusion_rule(self) -> None:
        """Include public functions and classes."""
        self.rules.append(
            ExtractedRule(
                name="include-public-functions",
                priority=500,
                description="Include public functions (not starting with underscore)",
                pattern=r"^[a-z_][a-z0-9_]*$",
                exact_match=None,
                member_type=MemberType.FUNCTION,
                action=RuleAction.INCLUDE,
                propagate=PropagationLevel.NONE,
                source_line=None,
            )
        )

        self.rules.append(
            ExtractedRule(
                name="include-public-classes",
                priority=500,
                description="Include public classes (CamelCase)",
                pattern=r"^[A-Z][a-zA-Z0-9]*$",
                exact_match=None,
                member_type=MemberType.CLASS,
                action=RuleAction.INCLUDE,
                propagate=PropagationLevel.NONE,
                source_line=None,
            )
        )

    def _extract_module_exceptions(self) -> None:
        """Placeholder for per-module overrides. Override to add custom entries."""

    def _generate_yaml(self) -> str:
        """Serialize rules to a YAML configuration string."""
        sorted_rules = sorted(self.rules, key=lambda r: (-r.priority, r.name))

        yaml_data: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "metadata": {
                "generated_by": "exportify init",
                "note": "Default configuration — edit rules to suit your project",
            },
            "rules": [],
        }

        for rule in sorted_rules:
            rule_mapping: dict[str, Any] = {
                "name": rule.name,
                "priority": rule.priority,
                "description": rule.description,
                "match": {},
                "action": rule.action.value,
            }

            if rule.pattern:
                rule_mapping["match"]["name_pattern"] = rule.pattern
            if rule.exact_match:
                rule_mapping["match"]["name_exact"] = rule.exact_match
            if rule.member_type:
                rule_mapping["match"]["member_type"] = rule.member_type.value
            if rule.propagate:
                rule_mapping["propagate"] = rule.propagate.value

            yaml_data["rules"].append(rule_mapping)

        if self.overrides_include or self.overrides_exclude:
            yaml_data["overrides"] = {}
        if self.overrides_include:
            yaml_data["overrides"]["include"] = self.overrides_include
        if self.overrides_exclude:
            yaml_data["overrides"]["exclude"] = self.overrides_exclude

        serialized = yaml.dump(
            yaml_data, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100
        )

        header = f"""# Exportify Default Configuration
# Generated by: exportify init
#
# Rules are evaluated in priority order (highest first); the first match wins.
# Edit this file to customize export behavior for your project.
#
# Schema: {SCHEMA_VERSION}
# Docs:   https://github.com/knitli/exportify

"""
        return header + serialized

    def _generate_summary(self) -> str:
        """Generate a human-readable summary of the generated configuration."""
        lines = [
            "# Exportify Configuration Summary",
            "",
            f"**Generated rules**: {len(self.rules)}",
            f"**Override modules**: {len(self.overrides_include) + len(self.overrides_exclude)}",
            "",
            "## Rules",
            "",
        ]

        for rule in sorted(self.rules, key=lambda r: (-r.priority, r.name)):
            lines = self._build_rule_details(lines, rule)
        lines += [
            "## Priority Bands",
            "",
            "| Priority | Purpose |",
            "|----------|---------|",
            "| 1000 | Absolute exclusions (private, dunders) |",
            "| 900–800 | Infrastructure/framework exclusions |",
            "| 700 | Primary export rules (classes, functions) |",
            "| 600–500 | Import handling |",
            "| 300–400 | Special cases |",
            "| 0–200 | Defaults/fallbacks |",
            "",
        ]

        return "\n".join(lines)

    def _build_rule_details(self, lines: list[str], rule: ExtractedRule) -> list[str]:
        """Append detailed information about a rule to the summary."""
        lines.extend((
            f"### {rule.name} (priority {rule.priority})",
            f"**Description**: {rule.description}",
            f"**Action**: `{rule.action.value}`",
        ))
        if rule.pattern:
            lines.append(f"**Pattern**: `{rule.pattern}`")
        if rule.exact_match:
            lines.append(f"**Exact match**: `{rule.exact_match}`")
        if rule.member_type:
            lines.append(f"**Member type**: `{rule.member_type.value}`")
        if rule.propagate:
            lines.append(f"**Propagation**: `{rule.propagate.value}`")
        lines.append("")
        return lines


def _rule_from_yaml(rule_dict: dict) -> ExtractedRule:
    """Parse a flat YAML rule dict into an ExtractedRule.

    For rules with complex ``any_of``/``all_of`` match blocks, only the
    top-level match fields (``name_pattern``, ``name_exact``, ``member_type``)
    are captured — this is sufficient for reporting purposes.
    """
    match_dict = rule_dict.get("match") or {}
    member_type_str = match_dict.get("member_type")
    propagate_str = rule_dict.get("propagate")
    action_str = rule_dict.get("action", "no_decision")
    return ExtractedRule(
        name=rule_dict["name"],
        priority=rule_dict.get("priority", 0),
        description=rule_dict.get("description", ""),
        pattern=match_dict.get("name_pattern"),
        exact_match=match_dict.get("name_exact"),
        member_type=MemberType(member_type_str) if member_type_str else None,
        action=RuleAction(action_str),
        propagate=PropagationLevel(propagate_str) if propagate_str else None,
        source_line=None,
    )


def _load_init_template() -> tuple[str, list[ExtractedRule]]:
    """Read the bundled default rules template and parse it into ExtractedRule objects."""
    template_path = Path(__file__).parent / "rules" / "default_rules.yaml"
    yaml_content = template_path.read_text(encoding="utf-8")
    data = yaml.safe_load(yaml_content)
    rules = [_rule_from_yaml(r) for r in data.get("rules", [])]
    return yaml_content, rules


def _generate_template_summary(rules: list[ExtractedRule]) -> str:
    """Return a human-readable summary of the template rules."""
    lines = [
        "# Exportify Configuration Summary",
        "",
        f"**Generated rules**: {len(rules)}",
        "",
        "## Rules",
        "",
    ]
    for rule in sorted(rules, key=lambda r: (-r.priority, r.name)):
        lines.extend([
            f"### {rule.name} (priority {rule.priority})",
            f"**Description**: {rule.description}",
            f"**Action**: `{rule.action.value}`",
        ])
        if rule.pattern:
            lines.append(f"**Pattern**: `{rule.pattern}`")
        if rule.member_type:
            lines.append(f"**Member type**: `{rule.member_type.value}`")
        if rule.propagate:
            lines.append(f"**Propagation**: `{rule.propagate.value}`")
        lines.append("")
    lines += [
        "## Priority Bands",
        "",
        "| Priority | Purpose |",
        "|----------|---------|",
        "| 1000 | Absolute exclusions (private, dunders) |",
        "| 900–800 | Infrastructure/framework exclusions |",
        "| 700 | Primary export rules (classes, functions, constants, type aliases) |",
        "| 600 | Import handling |",
        "| 400 | Variable handling |",
        "| 300 | Project-specific propagation overrides |",
        "| 0 | Default fallback |",
        "",
    ]
    return "\n".join(lines)


def migrate_to_yaml(
    output_path: Path = DEFAULT_OUTPUT, *, dry_run: bool = False
) -> MigrationResult:
    """Generate default exportify configuration and optionally write it.

    Loads the bundled ``default_rules.yaml`` — the full default rule set with
    correct propagation settings — and writes it to ``output_path``.

    Args:
        output_path: Destination for the YAML config file.
        dry_run: If True, generate but do not write any files.

    Returns:
        MigrationResult with YAML content and generation details.
    """
    yaml_content, rules = _load_init_template()
    summary = _generate_template_summary(rules)

    result = MigrationResult(
        yaml_content=yaml_content,
        rules_generated=rules,
        overrides_generated={"include": {}, "exclude": {}},
        summary=summary,
        success=True,
        errors=[],
    )

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(yaml_content, encoding="utf-8")

    return result


def _validate_private_member(name: str, result) -> list[str]:
    """Validate private member exclusion."""
    if result.action != RuleAction.EXCLUDE:
        return [f"Private member {name} not excluded: got {result.action.value}"]
    return []


def _validate_constant(name: str, result) -> list[str]:
    """Validate constant inclusion."""
    if result.action != RuleAction.INCLUDE:
        return [f"Constant {name} not included: got {result.action.value}"]
    return []


def _validate_exception_class(name: str, result) -> list[str]:
    """Validate exception class inclusion and propagation."""
    errors = []
    if result.action != RuleAction.INCLUDE:
        errors.append(f"Exception {name} not included: got {result.action.value}")
    if result.propagation != PropagationLevel.ROOT:
        errors.append(f"Exception {name} not propagated to root: got {result.propagation}")
    return errors


def _validate_public_member(name: str, result) -> list[str]:
    """Validate public member inclusion."""
    if result.action != RuleAction.INCLUDE:
        return [f"Public member {name} not included: got {result.action.value}"]
    return []


def _is_private(member_name: str) -> bool:
    """Return True if member name starts with an underscore."""
    return member_name.startswith("_")


def _is_constant(member_name: str, member_kind: MemberType) -> bool:
    """Return True if member is a SCREAMING_SNAKE_CASE constant."""
    return member_kind == MemberType.CONSTANT and bool(re.match(r"^[A-Z][A-Z0-9_]*$", member_name))


def _is_exception_class(member_name: str, member_kind: MemberType) -> bool:
    """Return True if member is an exception/error/warning class."""
    return member_kind == MemberType.CLASS and bool(
        re.match(r".*Error$|.*Exception$|.*Warning$", member_name)
    )


def verify_migration(
    yaml_path: Path = DEFAULT_OUTPUT, test_cases: list[tuple[str, str, MemberType]] | None = None
) -> tuple[bool, list[str]]:
    """Verify that a generated config produces the expected behavior.

    Args:
        yaml_path: Path to the generated YAML config.
        test_cases: Tuples of (symbol_name, module_path, member_type) to validate.
            Defaults to a standard set covering common symbol patterns.

    Returns:
        (success, errors) tuple.
    """
    from .export_manager.rules import RuleEngine

    engine = RuleEngine()
    try:
        engine.load_rules([yaml_path])
    except Exception as e:
        return False, [f"Failed to load rules: {e}"]

    if test_cases is None:
        test_cases = [
            ("_private_func", "mypackage.core", MemberType.FUNCTION),
            ("__dunder__", "mypackage.core", MemberType.FUNCTION),
            ("MAX_SIZE", "mypackage.config", MemberType.CONSTANT),
            ("ValidationError", "mypackage.exceptions", MemberType.CLASS),
            ("CustomException", "mypackage.tools", MemberType.CLASS),
            ("public_function", "mypackage.utils", MemberType.FUNCTION),
            ("PublicClass", "mypackage.core", MemberType.CLASS),
        ]

    errors: list[str] = []

    from exportify.common.types import DetectedSymbol, SourceLocation, SymbolProvenance

    for name, module, member_type in test_cases:
        symbol = DetectedSymbol(
            name=name,
            member_type=member_type,
            provenance=SymbolProvenance.DEFINED_HERE,
            location=SourceLocation(line=1),
            is_private=_is_private(name),
            original_source=None,
            original_name=None,
        )

        result = engine.evaluate(symbol, module)

        if _is_private(name):
            errors.extend(_validate_private_member(name, result))
        elif _is_constant(name, member_type):
            errors.extend(_validate_constant(name, result))
        elif _is_exception_class(name, member_type):
            errors.extend(_validate_exception_class(name, result))
        else:
            errors.extend(_validate_public_member(name, result))

    return not errors, errors


def cli_init(output: Path | None = None, *, dry_run: bool = False, verbose: bool = False) -> int:
    """CLI helper for the init command.

    Args:
        output: Output path for the YAML config.
        dry_run: If True, show output but don't write.
        verbose: If True, show the full configuration summary.

    Returns:
        Exit code (0 = success, 1 = failure).
    """
    output_path = output or DEFAULT_OUTPUT

    result = migrate_to_yaml(output_path, dry_run=dry_run)

    if not result.success:
        print("❌ Init failed:")
        for error in result.errors:
            print(f"  - {error}")
        return 1

    print("✅ Configuration generated!")
    print(f"   Rules: {len(result.rules_generated)}")

    if dry_run:
        print("\n📄 Generated YAML (dry run - not written):")
        print("─" * 80)
        print(result.yaml_content)
        print("─" * 80)
    else:
        print(f"\n📝 Written to: {output_path}")

    if verbose:
        print("\n" + result.summary)

    if not dry_run:
        print("\n🔍 Verifying config...")
        success, errors = verify_migration(output_path)
        if success:
            print("✅ Verification passed!")
        else:
            print("⚠️ Verification found issues:")
            for error in errors:
                print(f"  - {error}")
            return 1

    return 0


__all__ = (
    "DEFAULT_OUTPUT",
    "SCHEMA_VERSION",
    "ExtractedRule",
    "MigrationResult",
    "RuleMigrator",
    "cli_init",
    "migrate_to_yaml",
    "verify_migration",
)
