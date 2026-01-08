#!/bin/bash
set -e

echo "=================================================="
echo "Noodle 2 - Initialization Script"
echo "=================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${BLUE}[1/5] Checking prerequisites...${NC}"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "  ✓ Python $PYTHON_VERSION found"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is required but not installed"
    exit 1
fi
echo "  ✓ Docker found"

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "Error: Docker daemon is not running"
    exit 1
fi
echo "  ✓ Docker daemon is running"

# Install Python dependencies
echo ""
echo -e "${BLUE}[2/5] Installing Python dependencies...${NC}"

if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi

echo "  Activating virtual environment..."
source venv/bin/activate

echo "  Installing/upgrading pip..."
pip install --upgrade pip --quiet

echo "  Installing Ray..."
pip install "ray[default]>=2.0.0" --quiet

echo "  Installing other dependencies..."
pip install pyyaml requests docker matplotlib numpy --quiet

echo "  ✓ Python dependencies installed"

# Pull required Docker images
echo ""
echo -e "${BLUE}[3/5] Pulling required Docker images...${NC}"
echo "  This may take several minutes on first run..."

# Pull the primary OpenLane container
docker pull efabless/openlane:ci2504-dev-amd64 || {
    echo -e "${YELLOW}Warning: Could not pull Docker image. Will attempt to use cached version.${NC}"
}
echo "  ✓ Docker image ready"

# Initialize Ray cluster (single-node development mode)
echo ""
echo -e "${BLUE}[4/5] Starting Ray cluster (single-node development mode)...${NC}"

# Stop any existing Ray instance
ray stop &> /dev/null || true

# Start Ray head node with dashboard
echo "  Starting Ray head node..."
ray start --head --dashboard-host=0.0.0.0 --dashboard-port=8265

# Wait for dashboard to be ready
echo "  Waiting for Ray dashboard to be ready..."
sleep 3

# Get Ray status
RAY_ADDRESS=$(ray status 2>/dev/null | grep -oP '(?<=127.0.0.1:)\d+' | head -1 || echo "6379")

echo "  ✓ Ray cluster started"

# Verify setup
echo ""
echo -e "${BLUE}[5/5] Verifying setup...${NC}"

# Check Ray dashboard
if curl -s http://localhost:8265 > /dev/null 2>&1; then
    echo "  ✓ Ray dashboard is accessible"
else
    echo -e "${YELLOW}  ⚠ Ray dashboard may not be ready yet (still starting up)${NC}"
fi

# Check OpenROAD in container
if docker run --rm efabless/openlane:ci2504-dev-amd64 which openroad > /dev/null 2>&1; then
    echo "  ✓ OpenROAD is available in container"
else
    echo -e "${YELLOW}  ⚠ Could not verify OpenROAD in container${NC}"
fi

# Create artifact directories
mkdir -p artifacts
mkdir -p studies
echo "  ✓ Created artifact directories"

# Success message
echo ""
echo -e "${GREEN}=================================================="
echo "Noodle 2 Environment Ready!"
echo "==================================================${NC}"
echo ""
echo "Access Information:"
echo "  • Ray Dashboard: http://localhost:8265"
echo "  • Ray address: 127.0.0.1:${RAY_ADDRESS}"
echo ""
echo "Quick Start:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. View feature list: cat feature_list.json | jq '.[] | select(.passes == false) | .description' | head -10"
echo "  3. Access Ray dashboard: open http://localhost:8265"
echo ""
echo "Container Information:"
echo "  • Primary image: efabless/openlane:ci2504-dev-amd64"
echo "  • Included PDKs: Nangate45, ASAP7, Sky130A"
echo ""
echo "Cleanup:"
echo "  • Stop Ray: ray stop"
echo "  • Deactivate venv: deactivate"
echo ""
echo -e "${YELLOW}Note: This is single-node development mode. Multi-node clusters are supported but not required for development.${NC}"
echo ""
