#!/bin/bash
# Quick status check for noodle2 demo runs

echo "=========================================="
echo "Noodle2 Demo Status - $(date)"
echo "=========================================="

# Check if process is running
PID=$(pgrep -f "run_demo.py all")
if [ -n "$PID" ]; then
    echo "✓ Demo process running (PID: $PID)"
    RUNTIME=$(ps -o etime= -p $PID | tr -d ' ')
    echo "  Runtime: $RUNTIME"
else
    echo "✗ Demo process not running"
fi

echo ""
echo "Study Progress:"
echo "---------------"

for study in nangate45_extreme_demo asap7_extreme_demo sky130_extreme_demo; do
    telemetry="/home/captain/work/PhysicalDesign/noodle2/output/$study/telemetry/$study/event_stream.ndjson"
    if [ -f "$telemetry" ]; then
        # Count stages completed
        stages_completed=$(grep -c "stage_end" "$telemetry" 2>/dev/null || echo "0")
        stages_started=$(grep -c "stage_start" "$telemetry" 2>/dev/null || echo "0")
        trials_completed=$(grep -c "trial_end" "$telemetry" 2>/dev/null || echo "0")

        # Check for study_end
        if grep -q "study_end" "$telemetry" 2>/dev/null; then
            status="✓ COMPLETED"
        else
            status="⏳ In Progress"
        fi

        echo "$study:"
        echo "  Status: $status"
        echo "  Stages: $stages_completed/20 completed ($stages_started started)"
        echo "  Trials: $trials_completed completed"
    else
        echo "$study: Not started yet"
    fi
    echo ""
done

echo "Log tail (last 10 lines):"
echo "-------------------------"
tail -10 /tmp/noodle2_full_demo.log 2>/dev/null || echo "No log file found"
