#!/usr/bin/env python3
"""Quick test to verify ECO TCL generation after bug fixes."""

import sys
sys.path.insert(0, 'src')

from controller.eco import BufferInsertionECO, CellSwapECO, CellResizeECO

def test_cell_swap_eco():
    """Verify CellSwapECO generates valid TCL without find_timing_paths."""
    eco = CellSwapECO(path_count=50)
    tcl = eco.generate_tcl()

    # Should NOT contain the buggy command
    assert "find_timing_paths" not in tcl, "Still contains find_timing_paths!"
    assert "-nworst" not in tcl, "Still contains -nworst flag!"

    # Should contain repair_timing
    assert "repair_timing" in tcl, "Missing repair_timing command!"

    print("✓ CellSwapECO TCL generation is valid")
    print(f"\nGenerated TCL:\n{tcl}")
    return True

def test_buffer_insertion_eco():
    """Verify BufferInsertionECO generates valid TCL."""
    eco = BufferInsertionECO(max_capacitance=0.2)
    tcl = eco.generate_tcl()

    # Should NOT contain filter command (doesn't work reliably)
    assert "get_nets -filter" not in tcl, "Still contains get_nets -filter!"
    assert "capacitance >" not in tcl, "Still has capacitance filter!"

    # Should contain repair_design and repair_timing
    assert "repair_design" in tcl, "Missing repair_design command!"
    assert "repair_timing" in tcl, "Missing repair_timing command!"

    print("✓ BufferInsertionECO TCL generation is valid")
    print(f"\nGenerated TCL:\n{tcl}")
    return True

def test_cell_resize_eco():
    """Verify CellResizeECO still works (should be unchanged)."""
    eco = CellResizeECO(size_multiplier=1.5, max_paths=100)
    tcl = eco.generate_tcl()

    assert "repair_timing" in tcl, "Missing repair_timing command!"

    print("✓ CellResizeECO TCL generation is valid")
    return True

if __name__ == "__main__":
    try:
        test_cell_swap_eco()
        print()
        test_buffer_insertion_eco()
        print()
        test_cell_resize_eco()
        print("\n✅ All ECO TCL generation tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
