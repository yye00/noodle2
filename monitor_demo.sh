#!/bin/bash
# Monitor the Nangate45 extreme demo progress

LOG_FILE="nangate45_demo_session58.log"

echo "=== Demo Monitor ==="
echo "Checking: $LOG_FILE"
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found!"
    exit 1
fi

# Check if demo is still running
if ps aux | grep -v grep | grep -q "demo_nangate45_extreme.sh"; then
    echo "Status: RUNNING"
else
    echo "Status: COMPLETED or NOT RUNNING"
fi

echo ""
echo "=== Last 20 lines of log ==="
tail -20 "$LOG_FILE"

echo ""
echo "=== Progress indicators ==="
grep -i "stage\|trial\|survivor\|complete" "$LOG_FILE" | tail -10

echo ""
echo "=== Recent errors (if any) ==="
grep -i "error\|failed\|exception" "$LOG_FILE" | tail -5 || echo "No errors found"
