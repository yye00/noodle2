#!/bin/bash
# Sky130 Extreme -> Fixed Demo
# Runs ACTUAL Noodle 2 study execution with real OpenROAD trials
#
# IMPORTANT: This script executes ACTUAL study runs.
#            NO mocking. NO placeholders. Real execution only.
#            All visualizations are generated from real OpenROAD data.

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Noodle 2 - Sky130 Extreme Demo${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${CYAN}IMPORTANT: This runs ACTUAL study execution.${NC}"
echo -e "${CYAN}NO mocking. NO placeholders. Real OpenROAD trials.${NC}"
echo ""
echo "This demo showcases fixing an extremely broken Sky130 design:"
echo "  Initial: WNS ~ -2500ps, hot_ratio > 0.3"
echo "  Target:  WNS improvement > 50%, hot_ratio < 0.12"
echo ""
echo "Sky130-specific features:"
echo "  - Production-realistic Ibex design"
echo "  - Full observability stack"
echo "  - Complete audit trail"
echo ""

# Check for Python environment
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 not found${NC}"
    exit 1
fi

# Ensure we're in the right directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if available
if [ -f ".venv/bin/activate" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Run the actual demo
echo -e "${GREEN}Starting actual study execution...${NC}"
echo ""

python3 run_demo.py sky130 \
    --output-dir demo_output \
    --artifacts-root artifacts \
    --telemetry-root telemetry

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Demo completed successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Output directory: demo_output/sky130_extreme_demo"
    echo "Summary: demo_output/sky130_extreme_demo/summary.json"
    echo ""
    echo "Artifacts generated (from REAL execution):"
    echo "  - before/ directory with initial state metrics and visualizations"
    echo "  - after/ directory with final improved metrics"
    echo "  - comparison/ directory with differential visualizations"
    echo "  - stages/ directory with per-stage progression"
    echo "  - diagnosis/ directory with auto-diagnosis reports"
    echo ""
    echo -e "${CYAN}All visualizations are from actual OpenROAD data.${NC}"
    echo -e "${CYAN}Production-realistic Sky130 Ibex design.${NC}"
else
    echo ""
    echo -e "${RED}Demo failed with exit code: $EXIT_CODE${NC}"
    exit $EXIT_CODE
fi
