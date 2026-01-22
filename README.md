# Noodle 2 — Safety-Aware Orchestration for Physical Design Experimentation

**Noodle 2** is a production-quality, policy-driven orchestration system for large-scale physical design (PD) experimentation built on OpenROAD. It manages uncertainty, failure, and limited compute budgets while exploring Engineering Change Orders (ECOs) across complex, multi-stage design workflows.

## Executive Summary

Noodle 2 does **not** replace PD tools or algorithms. Instead, it provides a deterministic control plane that enables:
- Structured experimentation with ECOs
- Auditable decision-making
- Safe automation across multiple studies, stages, and design variants
- Policy-driven safety gates and failure containment
- Distributed execution via Ray with full observability

## Key Features

### Safety & Policy
- **Three safety domains**: `sandbox` (exploratory), `guarded` (production), `locked` (regression-only)
- **ECO classification by blast radius**: topology_neutral, placement_local, routing_affecting, global_disruptive
- **Automatic failure detection & containment**: at ECO, ECO-class, stage, or study scope
- **Run legality reports**: validate configuration before consuming compute

### Experiment Control
- **Multi-stage workflows**: arbitrary N-stage experiment graphs with sequential safety-gated progression
- **Deterministic case naming**: `<case_name>_<stage_index>_<derived_index>` for traceable lineage
- **Adaptive policy with memory**: ECO effectiveness tracking and prior accumulation (trusted/mixed/suspicious/unknown)
- **Trial budgets & survivor selection**: per-stage limits with configurable ranking policies

### Observability
- **Ray Dashboard integration**: first-class operator UI for distributed execution
- **Structured telemetry**: Study/Stage/Case-level artifacts with backward-compatible schemas
- **Artifact indexing**: deterministic trial artifact bundles with deep links
- **OpenROAD heatmap exports**: placement density, RUDY, routing congestion visualization
- **Case lineage graphs**: DAG visualization of derivation relationships

### Supported PDKs
- **Nangate45** (45nm educational reference)
- **ASAP7** (7nm advanced-node, high routing pressure)
- **Sky130** (130nm open-source production PDK)

All PDKs are pre-installed in the Docker container.

## Prerequisites

- **Python 3.10+**
- **Docker** (with daemon running)
- **8GB+ RAM** recommended for single-node development

## Quick Start

### 1. Initialize Environment

```bash
cd noodle2

# Run initialization (creates venv, installs dependencies, starts Ray)
./init.sh
```

The `init.sh` script will:
- Create Python virtual environment (`.venv/`)
- Install Ray and other Python dependencies
- Pull required Docker images
- Start a single-node Ray cluster

### 2. Run a Demo

```bash
# Nangate45 extreme timing demo
./demo_nangate45_extreme.sh

# ASAP7 extreme timing demo
./demo_asap7_extreme.sh

# Sky130 extreme timing demo
./demo_sky130_extreme.sh
```

Each demo:
- Uses YAML configuration from `studies/` directory
- Establishes baseline metrics from the design snapshot
- Runs 20 stages of ECO optimization trials
- Generates summary reports and visualizations

### 3. View Results

Results are written to `output/<study_name>/`:

```
output/nangate45_extreme_demo/
├── summary.json                    # Study results with ECO tracking and rollback info
├── eco_leaderboard.json            # ECO effectiveness rankings
├── lineage.dot                     # Case derivation graph (Graphviz DOT format)
├── comparison/
│   └── stage_progression.png       # Multi-row stage visualization with ECO badges
├── stages/
│   └── stage_*/stage_summary.json  # Per-stage summaries with ECO distribution
└── trials/                         # Raw trial artifacts (ODB, timing reports)
```

**Key Output Files:**

- **summary.json**: Contains `stage_eco_summary` showing which ECOs were most effective per stage, `recovery_info` for recovery attempts, and `rollback_info` if any rollbacks occurred
- **stage_progression.png**: Visual flow diagram showing stages in a multi-row grid (5 per row), with ECO badges, survivor counts, and degradation warnings
- **stage_summary.json**: Per-stage details including `eco_distribution` with success rates by ECO type

### 4. Access Ray Dashboard

Open **http://localhost:8265** to monitor trial execution in real-time.

---

## Project Structure

```
noodle2/
├── README.md                    # This file
├── init.sh                      # Environment setup (venv, Ray, Docker)
├── run_demo.py                  # Main study runner
├── demo_nangate45_extreme.sh    # Nangate45 demo launcher
├── demo_asap7_extreme.sh        # ASAP7 demo launcher
├── demo_sky130_extreme.sh       # Sky130 demo launcher
├── pyproject.toml               # Python project configuration
├── studies/                     # Study configurations and snapshots
│   ├── nangate45_extreme.yaml   # Nangate45 study config
│   ├── asap7_extreme.yaml       # ASAP7 study config
│   ├── sky130_extreme.yaml      # Sky130 study config
│   ├── nangate45_extreme_ibex/  # Nangate45 design snapshot
│   ├── asap7_extreme_ibex/      # ASAP7 design snapshot
│   └── sky130_extreme/          # Sky130 design snapshot
├── output/                      # Study outputs (created at runtime)
├── src/                         # Source code
│   ├── controller/              # Study orchestration, ECOs, safety
│   ├── trial_runner/            # OpenROAD/Docker execution
│   ├── parsers/                 # Timing & congestion report parsers
│   ├── telemetry/               # Structured logging & events
│   └── visualization/           # Heatmap and graph generation
├── tests/                       # Test suite
└── .venv/                       # Python virtual environment
```

---

## Running Studies

### Using Demo Scripts (Recommended)

Demo scripts are the easiest way to run studies:

```bash
./demo_nangate45_extreme.sh
./demo_asap7_extreme.sh
./demo_sky130_extreme.sh
```

Each script:
1. Activates the Python virtual environment
2. Invokes `run_demo.py` with the appropriate YAML config
3. Writes outputs to `output/`

### Using run_demo.py Directly

For more control, invoke `run_demo.py` directly:

```bash
# Activate virtual environment first
source .venv/bin/activate

# Run with YAML configuration (recommended)
python run_demo.py --config studies/nangate45_extreme.yaml --output-dir output

# List available YAML configurations
python run_demo.py --list-configs

# Run without Ray (sequential execution)
python run_demo.py --config studies/nangate45_extreme.yaml --no-ray

# Specify custom output directory
python run_demo.py --config studies/my_study.yaml --output-dir /path/to/output
```

### Command-Line Options

| Option | Description |
|--------|-------------|
| `--config PATH` | Path to YAML study configuration file |
| `--output-dir PATH` | Output directory for results (default: `output`) |
| `--no-ray` | Disable Ray parallel execution (run sequentially) |
| `--no-dashboard` | Disable Ray dashboard |
| `--list-configs` | List available YAML configuration files |

---

## Adding a New Study

### Step 1: Create a Design Snapshot

A snapshot is a directory containing the design state to optimize:

```
studies/my_design_snapshot/
├── design.odb           # OpenDB database (placed design)
├── design.sdc           # Timing constraints (SDC format)
├── run_sta.tcl          # STA script for metrics extraction
├── metadata.json        # Snapshot metadata
└── metrics.json         # Initial timing metrics (optional)
```

**Required files:**

1. **design.odb** - OpenROAD database with placed cells. This is the starting point for ECO optimization.

2. **design.sdc** - Standard timing constraints:
   ```tcl
   create_clock -name clk -period 10.0 [get_ports clk]
   set_input_delay -clock clk 0.5 [all_inputs]
   set_output_delay -clock clk 0.5 [all_outputs]
   ```

3. **run_sta.tcl** - Script to run STA and extract metrics:
   ```tcl
   # Load PDK libraries (paths inside ORFS container)
   set platform_dir "/OpenROAD-flow-scripts/flow/platforms/nangate45"
   read_lef "$platform_dir/lef/NangateOpenCellLibrary.tech.lef"
   read_lef "$platform_dir/lef/NangateOpenCellLibrary.macro.lef"
   read_liberty "$platform_dir/lib/NangateOpenCellLibrary_typical.lib"

   # Load design
   read_db /snapshot/design.odb

   # Read constraints
   read_sdc /snapshot/design.sdc

   # Run STA
   set wns [sta::worst_slack -max]
   set tns [sta::total_negative_slack -max]

   # Write metrics
   set fp [open /work/metrics.json w]
   puts $fp "{\"wns_ps\": [expr int($wns * 1000)], ...}"
   close $fp
   ```

4. **metadata.json** - Snapshot information:
   ```json
   {
     "design_name": "my_design",
     "pdk": "Nangate45",
     "clock_period_ns": 10.0,
     "created_at": "2024-01-15T10:30:00Z"
   }
   ```

### Step 2: Create YAML Configuration

Create `studies/my_study.yaml`:

```yaml
# Study metadata
study:
  name: "my_study"
  description: "Optimize timing on my design"
  author: "Your Name"
  version: "1.0.0"

# Design configuration
design:
  pdk: "Nangate45"                              # PDK name
  base_case_name: "my_design_base"              # Base case identifier
  snapshot_path: "studies/my_design_snapshot"   # Path to snapshot directory
  establish_baseline: true                       # Run STA to get actual metrics

# Safety configuration
safety:
  domain: "sandbox"      # Options: sandbox, guarded, locked
  check_legality: true
  block_on_illegal: true

# Execution configuration
execution:
  use_ray: true
  ray_dashboard: true
  trial_timeout_seconds: 1800

# Stage configuration
stages:
  count: 10                    # Number of stages
  defaults:
    trial_budget: 25           # Trials per stage
    survivor_count: 5          # Survivors per stage
    timeout_seconds: 1800
  survivor_progression:
    type: "funnel"             # Reduce survivors over stages
    start: 8
    end: 2

# Target improvements
targets:
  wns_improvement_percent: 30
  hot_ratio_target: 0.15

# Output configuration
output:
  dir: "output"
  visualizations: true
  keep_trial_artifacts: true
```

### Step 3: Run the Study

```bash
source .venv/bin/activate
python run_demo.py --config studies/my_study.yaml --output-dir output
```

---

## YAML Configuration Reference

### study (required)

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Study identifier (used in output paths) |
| `description` | string | Human-readable description |
| `author` | string | Study author |
| `version` | string | Configuration version |

### design (required)

| Field | Type | Description |
|-------|------|-------------|
| `pdk` | string | PDK name: `Nangate45`, `ASAP7`, or `Sky130` |
| `base_case_name` | string | Base case identifier |
| `snapshot_path` | string | Path to snapshot directory |
| `establish_baseline` | boolean | Run STA before Stage 0 to capture actual metrics |
| `initial_metrics` | object | Reference metrics (wns_ps, tns_ps, hot_ratio) |

### safety

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `domain` | string | `guarded` | Safety domain: `sandbox`, `guarded`, `locked` |
| `check_legality` | boolean | `true` | Validate config before execution |
| `block_on_illegal` | boolean | `true` | Block execution if config is illegal |

**Safety Domains:**

| Domain | Allowed ECO Classes | Use Case |
|--------|---------------------|----------|
| `sandbox` | All classes | Exploratory experimentation |
| `guarded` | No global_disruptive | Production-like safety |
| `locked` | topology_neutral only | Regression testing |

### execution

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_ray` | boolean | `true` | Enable Ray parallel execution |
| `ray_dashboard` | boolean | `true` | Enable Ray dashboard |
| `ray_dashboard_port` | integer | `8265` | Dashboard port |
| `max_concurrent_trials` | integer | `0` | Max concurrent trials (0 = unlimited) |
| `trial_timeout_seconds` | integer | `1800` | Per-trial timeout |

### stages

| Field | Type | Description |
|-------|------|-------------|
| `count` | integer | Number of stages (1-50) |
| `defaults.trial_budget` | integer | Trials per stage |
| `defaults.survivor_count` | integer | Survivors per stage |
| `defaults.timeout_seconds` | integer | Per-trial timeout |
| `survivor_progression.type` | string | `fixed`, `funnel`, or `custom` |
| `survivor_progression.start` | integer | Initial survivor count (funnel) |
| `survivor_progression.end` | integer | Final survivor count (funnel) |
| `overrides` | list | Per-stage override rules |

**Stage Overrides:**

```yaml
stages:
  overrides:
    - stages: [0, 1]
      allowed_eco_classes: ["topology_neutral", "placement_local"]
    - stages: "2+"
      allowed_eco_classes: ["topology_neutral", "placement_local", "routing_affecting", "global_disruptive"]
```

### prior_learning

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable ECO prior tracking |
| `filter_from_stage` | integer | `3` | Start filtering suspicious ECOs at this stage |
| `min_data_points` | integer | `3` | Minimum trials before assigning prior state |
| `trusted_threshold` | float | `0.8` | Success rate for "trusted" state |
| `suspicious_threshold` | float | `0.7` | Failure rate for "suspicious" state |
| `cross_project_db` | string | `null` | Path to cross-project prior database |

**Enhanced Learning Options:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_wns_weighted_selection` | boolean | `true` | Prioritize ECOs by WNS improvement magnitude (not just pass/fail) |
| `within_study_learning` | boolean | `true` | Use current study's successful ECOs to influence later stages |
| `cross_study_learning` | boolean | `false` | Load priors from other studies/PDKs (e.g., ASAP7 learns from Sky130) |
| `cross_study_weight` | float | `0.3` | Weight for cross-study priors (0.0-1.0, lower = less influence) |
| `check_anti_patterns` | boolean | `true` | Skip ECOs with known anti-patterns for current design context |
| `exploration_rate` | float | `0.15` | Fraction of trials reserved for exploration (try less-proven ECOs) |

**How Enhanced Learning Works:**

1. **WNS-Weighted Selection**: Instead of simple round-robin ECO selection, the executor tracks the actual WNS improvement each ECO achieves. ECOs that historically produce larger improvements are selected more frequently in later stages.

2. **Within-Study Learning**: As a study progresses, successful ECOs from earlier stages influence selection in later stages. If `buffer_insertion` improved WNS by 500ps in Stage 2, it gets a higher selection probability in Stage 5.

3. **Cross-Study Learning**: When enabled, priors from other PDKs/designs contribute to ECO selection. For example, ASAP7 studies can benefit from learnings on Nangate45 designs. The `cross_study_weight` controls how much influence cross-study data has (0.3 = 30% weight).

4. **Anti-Pattern Checking**: The system tracks ECO+context combinations that frequently fail. For example, if `vt_swap` fails >70% of the time when hot_ratio > 0.5, it will be skipped in similar contexts.

5. **Exploration Rate**: Even with strong priors, a fraction of trials (default 15%) are reserved for exploration—trying ECOs that haven't been proven yet. This prevents the system from getting stuck in local optima.

**Example Configuration:**

```yaml
prior_learning:
  enabled: true
  filter_from_stage: 3
  min_data_points: 3
  trusted_threshold: 0.8
  suspicious_threshold: 0.7
  # Enhanced learning
  use_wns_weighted_selection: true
  within_study_learning: true
  cross_study_learning: true       # Enable cross-PDK learning
  cross_study_weight: 0.3          # 30% influence from other PDKs
  check_anti_patterns: true
  exploration_rate: 0.15           # 15% exploration
```

### viability

Early failure detection and rollback configuration.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `abort_on_base_case_failure` | boolean | `true` | Abort study if base case fails |
| `min_improvement_threshold` | float | `0.0` | Minimum improvement required |
| `max_wns_degradation_ps` | integer | `null` | Max WNS degradation before abort |
| `abort_on_stage_failure` | boolean | `true` | Abort if all trials in stage fail |
| `enable_rollback` | boolean | `false` | Enable rollback to best known state |
| `rollback_threshold_ps` | integer | `50` | WNS degradation threshold for rollback |
| `enable_recovery` | boolean | `false` | Try re-applying successful ECOs before rollback |
| `recovery_trials` | integer | `5` | Number of recovery trials to attempt |
| `recovery_strategy` | string | `top_performers` | Recovery ECO selection strategy |

**Recovery Feature:**

When `enable_recovery: true`, the executor tracks which ECOs improved WNS during the study. If a regression is detected:

1. **Recovery attempt first**: Re-apply the most successful ECOs before triggering rollback
2. **If recovery succeeds**: Continue with the recovered state (no rollback needed)
3. **If recovery fails**: Fall back to rollback to best known state

**Recovery Strategies:**

| Strategy | Description |
|----------|-------------|
| `top_performers` | ECOs ranked by total WNS improvement achieved |
| `conservative` | Prefer safe ECOs (cell_resize, buffer_insertion, etc.) |
| `recent_successful` | ECOs from most recent stages that showed improvement |

**Rollback Feature:**

When `enable_rollback: true`, the executor tracks the best known timing state (best WNS achieved). If a stage degrades WNS by more than `rollback_threshold_ps` from the best known state, the next stage will start from the best known state instead of the current stage's survivors.

Example:
```yaml
viability:
  abort_on_base_case_failure: true
  abort_on_stage_failure: true
  # Recovery - try successful ECOs first
  enable_recovery: true
  recovery_trials: 5
  recovery_strategy: "top_performers"
  # Rollback - fall back to best known state if recovery fails
  enable_rollback: true
  rollback_threshold_ps: 100
```

This two-tier approach prevents a single bad ECO from derailing an otherwise successful optimization run:
- First tries to recover by re-applying known-good ECOs
- Only rolls back if recovery cannot restore timing

### targets

| Field | Type | Description |
|-------|------|-------------|
| `wns_improvement_percent` | float | Target WNS improvement percentage |
| `hot_ratio_target` | float | Target hot_ratio (fraction of timing-critical area) |

### output

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `dir` | string | `output` | Output directory |
| `visualizations` | boolean | `true` | Generate visualizations |
| `heatmaps` | boolean | `true` | Generate heatmap PNGs |
| `lineage_graph` | boolean | `true` | Generate case lineage DOT file |
| `eco_leaderboard` | boolean | `true` | Generate ECO effectiveness ranking |
| `keep_trial_artifacts` | boolean | `true` | Keep raw trial ODB/reports |

---

## ECO Reference

### ECO Classes

| Class | Blast Radius | Description |
|-------|--------------|-------------|
| `TOPOLOGY_NEUTRAL` | Minimal | No connectivity changes (resize, swap, pin swap) |
| `PLACEMENT_LOCAL` | Low | Localized placement changes (cloning, density) |
| `ROUTING_AFFECTING` | Medium | May affect routing (buffer insertion, repair) |
| `GLOBAL_DISRUPTIVE` | High | Large-scale changes (full optimization, TDP) |

### Available ECOs

**Base ECOs** (safe, applied early):
| ECO | Class | Description |
|-----|-------|-------------|
| `cell_resize` | TOPOLOGY_NEUTRAL | Resize cells on critical paths |
| `buffer_insertion` | TOPOLOGY_NEUTRAL | Insert buffers for slew/cap |
| `cell_swap` | TOPOLOGY_NEUTRAL | Swap cells for timing |
| `pin_swap` | TOPOLOGY_NEUTRAL | Swap equivalent pins |
| `gate_cloning` | PLACEMENT_LOCAL | Clone high-fanout gates |
| `placement_density` | PLACEMENT_LOCAL | Adjust placement density |
| `repair_design` | ROUTING_AFFECTING | Fix DRV violations |
| `buffer_removal` | TOPOLOGY_NEUTRAL | Remove unnecessary buffers |

**Aggressive ECOs** (applied in later stages):
| ECO | Class | Description |
|-----|-------|-------------|
| `full_optimization` | GLOBAL_DISRUPTIVE | Complete optimization pipeline |
| `aggressive_timing` | GLOBAL_DISRUPTIVE | Maximum timing repair |
| `timing_driven_placement` | GLOBAL_DISRUPTIVE | Re-optimize placement |
| `sequential_repair` | ROUTING_AFFECTING | DRV then timing repair |
| `multi_pass_timing` | ROUTING_AFFECTING | Iterative timing with decaying margins |
| `hold_repair` | ROUTING_AFFECTING | Fix hold violations |
| `vt_swap` | TOPOLOGY_NEUTRAL | Swap VT variants (LVT/SVT/HVT) |

---

## Supported Tooling

### Docker Container

Noodle 2 executes trials inside Docker containers with pre-installed PDKs:

- **Container**: `efabless/openlane` or ORFS-compatible image
- **OpenROAD**: Full flow including placement, routing, STA
- **OpenSTA**: Static timing analysis
- **PDKs**: Nangate45, ASAP7, Sky130HD pre-installed

### Ray Cluster

Ray provides distributed execution:

```bash
# Start Ray (done by init.sh)
ray start --head --dashboard-host=0.0.0.0

# Stop Ray
ray stop

# Check Ray status
ray status
```

Dashboard: **http://localhost:8265**

### Python Environment

```bash
# Activate environment
source .venv/bin/activate

# Install additional dependencies
pip install <package>

# Run tests
pytest tests/
```

---

## PDK-Specific Notes

### Nangate45
- 45nm educational PDK
- Fast execution (good for development)
- Metal layers: `metal1` through `metal10`

### ASAP7
- 7nm predictive PDK
- High routing pressure, timing-critical
- Metal layers: `M1` through `M9` (uppercase)
- Requires explicit routing layer configuration

### Sky130
- 130nm open-source production PDK
- Metal layers: `li1`, `met1` through `met5` (abbreviated naming)
- Longer gate delays, different optimization characteristics

---

## Common Tasks

### Start/Stop Ray

```bash
# Start Ray cluster
ray start --head --dashboard-host=0.0.0.0

# Stop Ray cluster
ray stop
```

### Clean Output Directory

```bash
rm -rf output/*
```

### View Study Summary

```bash
cat output/nangate45_extreme_demo/summary.json | jq .
```

### Convert Lineage Graph to PNG

```bash
dot -Tpng output/nangate45_extreme_demo/lineage.dot -o lineage.png
```

---

## Troubleshooting

### Ray Dashboard Won't Start

```
ERROR: Failed to start the dashboard
```

This is usually non-fatal. Ray will continue without the dashboard. Check if port 8265 is in use.

### Docker Permission Denied

```bash
# Add user to docker group
sudo usermod -aG docker $USER
# Then log out and back in
```

### Trial Timeout

Increase timeout in YAML:
```yaml
execution:
  trial_timeout_seconds: 3600  # 1 hour
```

---

## License

MIT License

---

## Contact

For issues and feature requests, open a GitHub issue.

---

**Remember**: Noodle 2 is not an optimizer. It is the control plane that makes optimization trustworthy at scale.
