"""Tests for immutable design rules (F095, F096, F097)."""

import pytest

from src.controller.immutable_rules import (
    CellProtectionPattern,
    CellRules,
    ImmutabilityChecker,
    ImmutableRules,
    ImmutableViolation,
    NetRules,
    StructuralRules,
    TimingRules,
    ViolationSeverity,
    load_immutable_rules_from_config,
)


class TestStructuralRules:
    """Tests for structural immutability rules."""

    def test_create_structural_rules(self) -> None:
        """Test creating structural rules."""
        rules = StructuralRules(
            macro_locations=True,
            io_pin_positions=True,
            power_grid=False,
            clock_tree_topology=False,
        )

        assert rules.macro_locations is True
        assert rules.io_pin_positions is True
        assert rules.power_grid is False
        assert rules.clock_tree_topology is False

    def test_structural_rules_from_dict(self) -> None:
        """Test creating structural rules from dictionary."""
        data = {
            "macro_locations": True,
            "io_pin_positions": False,
            "power_grid": True,
        }

        rules = StructuralRules.from_dict(data)

        assert rules.macro_locations is True
        assert rules.io_pin_positions is False
        assert rules.power_grid is True
        assert rules.clock_tree_topology is False  # default


class TestTimingRules:
    """Tests for timing immutability rules."""

    def test_create_timing_rules(self) -> None:
        """Test creating timing rules."""
        rules = TimingRules(
            clock_definitions=True,
            false_paths=True,
            multicycle_paths=False,
        )

        assert rules.clock_definitions is True
        assert rules.false_paths is True
        assert rules.multicycle_paths is False

    def test_timing_rules_from_dict(self) -> None:
        """Test creating timing rules from dictionary."""
        data = {
            "clock_definitions": True,
            "multicycle_paths": True,
        }

        rules = TimingRules.from_dict(data)

        assert rules.clock_definitions is True
        assert rules.false_paths is False  # default
        assert rules.multicycle_paths is True


class TestNetRules:
    """Tests for net immutability rules."""

    def test_create_net_rules(self) -> None:
        """Test creating net rules."""
        rules = NetRules(protected_nets=["clk*", "reset*", "vdd*", "vss*"])

        assert len(rules.protected_nets) == 4
        assert "clk*" in rules.protected_nets

    def test_net_rules_from_dict(self) -> None:
        """Test creating net rules from dictionary."""
        data = {"protected_nets": ["clk*", "reset*"]}

        rules = NetRules.from_dict(data)

        assert len(rules.protected_nets) == 2
        assert "clk*" in rules.protected_nets

    def test_is_net_protected_exact_match(self) -> None:
        """Test net protection with exact match."""
        rules = NetRules(protected_nets=["clk_main"])

        assert rules.is_net_protected("clk_main") is True
        assert rules.is_net_protected("clk_secondary") is False

    def test_is_net_protected_wildcard(self) -> None:
        """Test net protection with wildcard patterns."""
        rules = NetRules(protected_nets=["clk*", "reset*", "vdd*", "vss*"])

        # Should match
        assert rules.is_net_protected("clk_main") is True
        assert rules.is_net_protected("clk0") is True
        assert rules.is_net_protected("reset_n") is True
        assert rules.is_net_protected("vdd_core") is True
        assert rules.is_net_protected("vss_io") is True

        # Should not match
        assert rules.is_net_protected("data_bus") is False
        assert rules.is_net_protected("addr_line") is False


class TestCellProtectionPattern:
    """Tests for cell protection patterns."""

    def test_pattern_match(self) -> None:
        """Test pattern-based matching."""
        protection = CellProtectionPattern(pattern="*_macro")

        assert protection.matches("memory_macro") is True
        assert protection.matches("cache_macro") is True
        assert protection.matches("standard_cell") is False

    def test_instance_match(self) -> None:
        """Test instance-based matching."""
        protection = CellProtectionPattern(instance="pll_inst")

        assert protection.matches("pll_inst") is True
        assert protection.matches("pll_inst_2") is False
        assert protection.matches("other_inst") is False

    def test_pattern_and_instance(self) -> None:
        """Test matching with both pattern and instance."""
        protection = CellProtectionPattern(pattern="pad_*", instance="special_pad")

        assert protection.matches("pad_north") is True
        assert protection.matches("special_pad") is True
        assert protection.matches("normal_cell") is False

    def test_from_dict(self) -> None:
        """Test creating from dictionary."""
        data = {"pattern": "*_macro", "instance": "pll_inst"}

        protection = CellProtectionPattern.from_dict(data)

        assert protection.pattern == "*_macro"
        assert protection.instance == "pll_inst"


class TestCellRules:
    """Tests for cell immutability rules."""

    def test_create_cell_rules(self) -> None:
        """Test creating cell rules."""
        protected = [
            CellProtectionPattern(pattern="*_macro"),
            CellProtectionPattern(instance="pll_inst"),
        ]

        rules = CellRules(protected_cells=protected)

        assert len(rules.protected_cells) == 2

    def test_cell_rules_from_dict_with_patterns(self) -> None:
        """Test creating cell rules from dictionary with pattern objects."""
        data = {
            "protected_cells": [
                {"pattern": "*_macro"},
                {"pattern": "pad_*"},
                {"instance": "pll_inst"},
            ]
        }

        rules = CellRules.from_dict(data)

        assert len(rules.protected_cells) == 3
        assert rules.is_cell_protected("memory_macro") is True
        assert rules.is_cell_protected("pad_north") is True
        assert rules.is_cell_protected("pll_inst") is True

    def test_cell_rules_from_dict_with_strings(self) -> None:
        """Test creating cell rules from dictionary with pattern strings."""
        data = {"protected_cells": ["*_macro", "pad_*"]}

        rules = CellRules.from_dict(data)

        assert len(rules.protected_cells) == 2
        assert rules.is_cell_protected("cache_macro") is True
        assert rules.is_cell_protected("pad_south") is True

    def test_is_cell_protected(self) -> None:
        """Test checking if cell is protected."""
        rules = CellRules(
            protected_cells=[
                CellProtectionPattern(pattern="*_macro"),
                CellProtectionPattern(pattern="pad_*"),
                CellProtectionPattern(instance="pll_inst"),
            ]
        )

        # Should be protected
        assert rules.is_cell_protected("memory_macro") is True
        assert rules.is_cell_protected("pad_north") is True
        assert rules.is_cell_protected("pll_inst") is True

        # Should not be protected
        assert rules.is_cell_protected("standard_cell") is False
        assert rules.is_cell_protected("buf_x4") is False

    def test_is_cell_size_locked(self) -> None:
        """Test checking if cell size is locked."""
        rules = CellRules(
            size_locked=[
                CellProtectionPattern(pattern="clkbuf_*"),
            ]
        )

        assert rules.is_cell_size_locked("clkbuf_1") is True
        assert rules.is_cell_size_locked("clkbuf_large") is True
        assert rules.is_cell_size_locked("buf_x2") is False


class TestImmutableRules:
    """Tests for complete immutable rules."""

    def test_create_empty_rules(self) -> None:
        """Test creating empty (disabled) rules."""
        rules = ImmutableRules()

        assert rules.structural.macro_locations is False
        assert len(rules.nets.protected_nets) == 0

    def test_create_rules_with_components(self) -> None:
        """Test creating rules with all components."""
        rules = ImmutableRules(
            structural=StructuralRules(macro_locations=True),
            nets=NetRules(protected_nets=["clk*"]),
            cells=CellRules(
                protected_cells=[CellProtectionPattern(pattern="*_macro")]
            ),
        )

        assert rules.structural.macro_locations is True
        assert len(rules.nets.protected_nets) == 1
        assert len(rules.cells.protected_cells) == 1

    def test_from_dict(self) -> None:
        """Test creating rules from dictionary."""
        data = {
            "structural": {"macro_locations": True, "io_pin_positions": True},
            "timing": {"clock_definitions": True},
            "nets": {"protected_nets": ["clk*", "reset*", "vdd*", "vss*"]},
            "cells": {
                "protected_cells": [
                    {"pattern": "*_macro"},
                    {"pattern": "pad_*"},
                    {"instance": "pll_inst"},
                ],
                "size_locked": [{"pattern": "clkbuf_*"}],
            },
        }

        rules = ImmutableRules.from_dict(data)

        assert rules.structural.macro_locations is True
        assert rules.structural.io_pin_positions is True
        assert rules.timing.clock_definitions is True
        assert len(rules.nets.protected_nets) == 4
        assert len(rules.cells.protected_cells) == 3
        assert len(rules.cells.size_locked) == 1

    def test_disabled_rules(self) -> None:
        """Test creating disabled rules."""
        rules = ImmutableRules.disabled()

        assert rules.structural.macro_locations is False
        assert rules.structural.io_pin_positions is False
        assert len(rules.nets.protected_nets) == 0


class TestImmutabilityChecker:
    """Tests for immutability checker."""

    def test_check_macro_move_allowed(self) -> None:
        """Test macro move when allowed."""
        rules = ImmutableRules(structural=StructuralRules(macro_locations=False))
        checker = ImmutabilityChecker(rules)

        violation = checker.check_macro_move("my_macro")

        assert violation is None

    def test_check_macro_move_blocked(self) -> None:
        """Test macro move when blocked (F095)."""
        rules = ImmutableRules(structural=StructuralRules(macro_locations=True))
        checker = ImmutabilityChecker(rules)

        violation = checker.check_macro_move("my_macro")

        assert violation is not None
        assert violation.rule_type == "structural.macro_locations"
        assert violation.target == "my_macro"
        assert violation.severity == ViolationSeverity.CRITICAL
        assert "immutable" in violation.reason.lower()

    def test_check_net_modification_allowed(self) -> None:
        """Test net modification when allowed."""
        rules = ImmutableRules(nets=NetRules(protected_nets=["clk*"]))
        checker = ImmutabilityChecker(rules)

        # data_bus is not protected
        violation = checker.check_net_modification("data_bus")

        assert violation is None

    def test_check_net_modification_blocked(self) -> None:
        """Test net modification when blocked (F096)."""
        rules = ImmutableRules(
            nets=NetRules(protected_nets=["clk*", "reset*", "vdd*", "vss*"])
        )
        checker = ImmutabilityChecker(rules)

        # Clock net should be protected
        violation = checker.check_net_modification("clk_main")

        assert violation is not None
        assert violation.rule_type == "nets.protected_nets"
        assert violation.target == "clk_main"
        assert violation.severity == ViolationSeverity.CRITICAL
        assert "protected" in violation.reason.lower()

    def test_check_cell_modification_allowed(self) -> None:
        """Test cell modification when allowed."""
        rules = ImmutableRules(
            cells=CellRules(
                protected_cells=[CellProtectionPattern(pattern="*_macro")]
            )
        )
        checker = ImmutabilityChecker(rules)

        # Standard cell is not protected
        violation = checker.check_cell_modification("buf_x4")

        assert violation is None

    def test_check_cell_modification_blocked(self) -> None:
        """Test cell modification when blocked (F097)."""
        rules = ImmutableRules(
            cells=CellRules(
                protected_cells=[
                    CellProtectionPattern(pattern="*_macro"),
                    CellProtectionPattern(pattern="pad_*"),
                    CellProtectionPattern(instance="pll_inst"),
                ]
            )
        )
        checker = ImmutabilityChecker(rules)

        # Macro should be protected
        violation = checker.check_cell_modification("memory_macro", "resize")

        assert violation is not None
        assert violation.rule_type == "cells.protected_cells"
        assert violation.target == "memory_macro"
        assert violation.severity == ViolationSeverity.CRITICAL

        # Pad should be protected
        violation = checker.check_cell_modification("pad_north", "move")

        assert violation is not None
        assert violation.target == "pad_north"

        # Specific instance should be protected
        violation = checker.check_cell_modification("pll_inst", "modify")

        assert violation is not None
        assert violation.target == "pll_inst"

    def test_check_cell_resize_size_locked(self) -> None:
        """Test cell resize when size is locked."""
        rules = ImmutableRules(
            cells=CellRules(size_locked=[CellProtectionPattern(pattern="clkbuf_*")])
        )
        checker = ImmutabilityChecker(rules)

        # Resize should be blocked for size-locked cells
        violation = checker.check_cell_modification("clkbuf_1", "resize")

        assert violation is not None
        assert violation.rule_type == "cells.size_locked"
        assert violation.target == "clkbuf_1"
        assert "size is locked" in violation.reason.lower()

    def test_check_clock_definition_change_allowed(self) -> None:
        """Test clock definition change when allowed."""
        rules = ImmutableRules(timing=TimingRules(clock_definitions=False))
        checker = ImmutabilityChecker(rules)

        violation = checker.check_clock_definition_change("clk_main")

        assert violation is None

    def test_check_clock_definition_change_blocked(self) -> None:
        """Test clock definition change when blocked."""
        rules = ImmutableRules(timing=TimingRules(clock_definitions=True))
        checker = ImmutabilityChecker(rules)

        violation = checker.check_clock_definition_change("clk_main")

        assert violation is not None
        assert violation.rule_type == "timing.clock_definitions"
        assert violation.severity == ViolationSeverity.CRITICAL

    def test_check_io_pin_move_allowed(self) -> None:
        """Test I/O pin move when allowed."""
        rules = ImmutableRules(structural=StructuralRules(io_pin_positions=False))
        checker = ImmutabilityChecker(rules)

        violation = checker.check_io_pin_move("din[0]")

        assert violation is None

    def test_check_io_pin_move_blocked(self) -> None:
        """Test I/O pin move when blocked."""
        rules = ImmutableRules(structural=StructuralRules(io_pin_positions=True))
        checker = ImmutabilityChecker(rules)

        violation = checker.check_io_pin_move("din[0]")

        assert violation is not None
        assert violation.rule_type == "structural.io_pin_positions"
        assert violation.severity == ViolationSeverity.CRITICAL


class TestViolationSerialization:
    """Tests for violation serialization."""

    def test_violation_to_dict(self) -> None:
        """Test converting violation to dictionary."""
        violation = ImmutableViolation(
            rule_type="structural.macro_locations",
            target="my_macro",
            reason="Cannot move macro",
            severity=ViolationSeverity.CRITICAL,
        )

        data = violation.to_dict()

        assert data["rule_type"] == "structural.macro_locations"
        assert data["target"] == "my_macro"
        assert data["reason"] == "Cannot move macro"
        assert data["severity"] == "critical"


class TestLoadFromConfig:
    """Tests for loading rules from config."""

    def test_load_with_immutable_rules(self) -> None:
        """Test loading when immutable_rules present in config."""
        config = {
            "immutable_rules": {
                "structural": {"macro_locations": True},
                "nets": {"protected_nets": ["clk*", "reset*"]},
            }
        }

        rules = load_immutable_rules_from_config(config)

        assert rules.structural.macro_locations is True
        assert len(rules.nets.protected_nets) == 2

    def test_load_without_immutable_rules(self) -> None:
        """Test loading when immutable_rules not present (disabled)."""
        config = {"study": {"name": "test"}}

        rules = load_immutable_rules_from_config(config)

        # Should get disabled rules
        assert rules.structural.macro_locations is False
        assert len(rules.nets.protected_nets) == 0


class TestEndToEndScenarios:
    """End-to-end tests for immutability checking."""

    def test_f095_macro_location_protection(self) -> None:
        """F095: Test complete workflow for macro location protection."""
        # Step 1: Configure immutable_rules.structural.macro_locations: true
        config = {
            "immutable_rules": {"structural": {"macro_locations": True}}
        }
        rules = load_immutable_rules_from_config(config)

        # Step 2: Create checker
        checker = ImmutabilityChecker(rules)

        # Step 3: Define ECO that attempts to move a macro
        macro_name = "sram_bank_0"

        # Step 4: Run legality check before ECO execution
        violation = checker.check_macro_move(macro_name)

        # Step 5: Verify ECO is BLOCKED with immutable_violation error
        assert violation is not None
        assert violation.rule_type == "structural.macro_locations"
        assert violation.target == macro_name

        # Step 6: Verify violation severity is critical
        assert violation.severity == ViolationSeverity.CRITICAL

    def test_f096_net_pattern_protection(self) -> None:
        """F096: Test complete workflow for net pattern protection."""
        # Step 1: Configure protected_nets: [clk*, reset*, vdd*, vss*]
        config = {
            "immutable_rules": {
                "nets": {"protected_nets": ["clk*", "reset*", "vdd*", "vss*"]}
            }
        }
        rules = load_immutable_rules_from_config(config)

        # Step 2: Create checker
        checker = ImmutabilityChecker(rules)

        # Step 3: Define ECO that attempts to modify a clock net
        clock_net = "clk_main"

        # Step 4: Run mutation permission check
        violation = checker.check_net_modification(clock_net)

        # Step 5: Verify ECO is blocked with net protection violation
        assert violation is not None
        assert violation.rule_type == "nets.protected_nets"
        assert violation.target == clock_net

        # Step 6: Verify non-protected nets can still be modified
        data_net = "data_bus[0]"
        violation = checker.check_net_modification(data_net)
        assert violation is None

    def test_f097_cell_pattern_and_instance_protection(self) -> None:
        """F097: Test complete workflow for cell pattern and instance protection."""
        # Step 1: Configure protected_cells with patterns and instances
        config = {
            "immutable_rules": {
                "cells": {
                    "protected_cells": [
                        {"pattern": "*_macro"},
                        {"pattern": "pad_*"},
                        {"instance": "pll_inst"},
                    ]
                }
            }
        }
        rules = load_immutable_rules_from_config(config)

        # Step 2: Create checker
        checker = ImmutabilityChecker(rules)

        # Step 3: Define ECO that attempts to resize a protected cell
        macro_cell = "memory_macro"

        # Step 4: Run mutation permission check
        violation = checker.check_cell_modification(macro_cell, "resize")

        # Step 5: Verify ECO is blocked for protected cells
        assert violation is not None
        assert violation.rule_type == "cells.protected_cells"
        assert violation.target == macro_cell

        # Also test pad protection
        pad_cell = "pad_north_0"
        violation = checker.check_cell_modification(pad_cell, "move")
        assert violation is not None
        assert violation.target == pad_cell

        # Also test instance protection
        pll_inst = "pll_inst"
        violation = checker.check_cell_modification(pll_inst, "modify")
        assert violation is not None
        assert violation.target == pll_inst

        # Step 6: Verify standard cells can still be modified per ECO class
        standard_cell = "buf_x4_inst"
        violation = checker.check_cell_modification(standard_cell, "resize")
        assert violation is None
