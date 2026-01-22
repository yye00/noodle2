#!/bin/bash
# Sky130 Extreme Demo
# Runs Noodle 2 study using YAML configuration
#
# Configuration: studies/sky130_extreme.yaml
# See the YAML file for all study parameters (stages, ECOs, thresholds)

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
echo -e "${CYAN}Configuration: studies/sky130_extreme.yaml${NC}"
echo -e "${CYAN}See YAML for study parameters (stages, ECOs, metrics)${NC}"
echo ""
echo "This demo runs actual OpenROAD trials to fix timing violations"
echo "on a Sky130 GCD design (open-source 130nm PDK)."
echo ""
echo "Sky130 characteristics:"
echo "  - Open-source production PDK"
echo "  - 130nm process node"
echo "  - Full OpenROAD flow compatibility"
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
    echo -e "${YELLOW}Activating virtual environment (.venv)...${NC}"
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    echo -e "${YELLOW}Activating virtual environment (venv)...${NC}"
    source venv/bin/activate
fi

# Run using YAML configuration
echo -e "${GREEN}Starting study execution...${NC}"
echo ""

python3 run_demo.py --config studies/sky130_extreme.yaml --output-dir output

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Demo completed successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Outputs: output/sky130_extreme_demo/"
    echo ""
    echo "Key files:"
    echo "  summary.json        - Study results and metrics"
    echo "  eco_leaderboard.json - ECO effectiveness rankings"
    echo "  trials/             - Raw trial artifacts"
    echo ""
else
    echo ""
    echo -e "${RED}Demo failed with exit code: $EXIT_CODE${NC}"
    exit $EXIT_CODE
fi
