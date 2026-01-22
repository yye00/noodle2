#!/bin/bash
echo "=========================================="
echo "Microwatt Build Status - $(date)"
echo "=========================================="

# Check if container is running
if docker ps | grep -q orfs_microwatt_build; then
    echo "✓ Build container running"
    
    # Get current stage from log
    if [ -f /home/captain/work/PhysicalDesign/noodle2/studies/sky130_microwatt/build.log ]; then
        echo ""
        echo "Current stage:"
        grep -E "^(Entering|Leaving|mkdir|make\[)" /home/captain/work/PhysicalDesign/noodle2/studies/sky130_microwatt/build.log | tail -5
        echo ""
        echo "Last 10 lines:"
        tail -10 /home/captain/work/PhysicalDesign/noodle2/studies/sky130_microwatt/build.log
    fi
else
    echo "✗ Build container not running"
    
    # Check if ODB was created
    if [ -f /home/captain/work/PhysicalDesign/noodle2/studies/sky130_microwatt/microwatt_placed.odb ]; then
        echo "✓ microwatt_placed.odb created!"
        ls -lh /home/captain/work/PhysicalDesign/noodle2/studies/sky130_microwatt/microwatt_placed.odb
    else
        echo "Checking for any ODB files..."
        ls -la /home/captain/work/PhysicalDesign/noodle2/studies/sky130_microwatt/*.odb 2>/dev/null || echo "No ODB files found yet"
    fi
    
    # Check exit status
    echo ""
    echo "Build log tail:"
    tail -20 /home/captain/work/PhysicalDesign/noodle2/studies/sky130_microwatt/build.log 2>/dev/null
fi
