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
- **Nangate45** (fast bring-up, educational reference)
- **ASAP7** (advanced-node, high routing pressure)
- **Sky130/Sky130A** (open-source production PDK)

All PDKs are pre-installed in the container (`efabless/openlane:ci2504-dev-amd64`).

## Prerequisites

- **Python 3.10+**
- **Docker** (with daemon running)
- **8GB+ RAM** recommended for single-node development
- **X11 server** (optional, for GUI-based heatmap exports)

## Quick Start

### 1. Clone and Initialize

```bash
# Clone the repository (or extract the archive)
cd noodle2

# Make init script executable
chmod +x init.sh

# Run initialization (installs dependencies, starts Ray)
./init.sh
```

The `init.sh` script will:
- Create a Python virtual environment
- Install Ray and other dependencies
- Pull the required Docker images
- Start a single-node Ray cluster
- Verify the setup

### 2. Activate Environment

```bash
source venv/bin/activate
```

### 3. Access Ray Dashboard

Open your browser to: **http://localhost:8265**

You'll see the Ray cluster status and can monitor trial execution in real-time.

## Project Structure

```
noodle2/
├── README.md                 # This file
├── app_spec.txt             # Complete product specification
├── feature_list.json        # 200+ test cases (single source of truth)
├── init.sh                  # Environment setup script
├── venv/                    # Python virtual environment (created by init.sh)
├── artifacts/               # Study artifacts directory
├── studies/                 # Study definitions directory
└── src/                     # Source code (to be implemented)
    ├── controller/          # Study orchestration logic
    ├── trial_runner/        # OpenROAD execution wrapper
    ├── parsers/             # Timing & congestion report parsers
    ├── policy/              # Safety & ranking policies
    ├── telemetry/           # Structured logging & artifact indexing
    └── visualization/       # Heatmap rendering & graph generation
```

## Development Workflow

### Feature-Driven Development

All development is tracked via `feature_list.json`, which contains **205 detailed test cases** covering:
- **Functional features** (175): core system capabilities
- **Style features** (30): UI/UX and observability requirements

Each feature has:
- `category`: "functional" or "style"
- `description`: what the feature does
- `steps`: detailed test steps (2-12 steps each)
- `passes`: boolean (initially `false`, set to `true` when implemented and verified)

**CRITICAL**: Never remove or edit features. Only mark as passing.

### Check Progress

```bash
# View all pending features
cat feature_list.json | jq '.[] | select(.passes == false) | .description'

# Count completion
cat feature_list.json | jq '[.[] | select(.passes == true)] | length'

# View features by category
cat feature_list.json | jq '.[] | select(.category == "functional" and .passes == false) | .description' | head -20
```

### Implementation Priority

Features are ordered by priority in `feature_list.json`. Start from the top:

1. **Gate 0: Baseline viability** (features 1-10)
   - Ray cluster initialization
   - Base case execution
   - Report parsing
   - Failure detection

2. **Gate 1: Full output contract** (features 11-50)
   - Telemetry emission
   - Artifact indexing
   - Safety gates
   - Multi-stage execution

3. **Gate 2: Controlled failure injection** (features 51-100)
   - Failure classification
   - Containment scopes
   - Abort triggers
   - ECO memory

4. **Gates 3-4: Cross-target parity & extreme scenarios** (features 101-200+)

### Validation Ladder

Noodle 2 follows a strict staged validation ladder:

**Gate 0**: Base case must run for each PDK (Nangate45, ASAP7, Sky130) or stop
**Gate 1**: Full observability contract on basic config (timing, congestion, telemetry)
**Gate 2**: Controlled regression/failure injection on fast targets
**Gate 3**: Cross-target parity (same contracts on all PDKs)
**Gate 4**: Extreme scenarios (severe violations, adversarial conditions)

## Core Concepts

### Study
Top-level unit of work defining:
- Base design snapshot
- Safety domain
- Policy and rail configuration
- One or more multi-stage experiment graphs

### Case
Concrete design state derived from a Study:
- Base case = original snapshot
- Derived cases = base + ECO sequence
- Forms a DAG within Study
- Naming: `<case_name>_<stage_index>_<derived_index>`

### Stage
Refinement phase within Study:
- Execution mode (STA-only, STA+congestion, etc.)
- Trial budget and survivor count
- Allowed ECO classes
- Abort and safety thresholds

### ECO (Engineering Change Order)
First-class auditable unit of change:
- Stable name and classification
- Emits metrics, logs, failure semantics
- Comparable across cases and studies
- Belongs to ECO class with defined risk envelope

## Technology Stack

- **Python 3.10+**: Core controller and policy logic
- **Ray**: Distributed execution and scheduling
- **Docker**: Isolated trial execution (efabless/openlane:ci2504-dev-amd64)
- **OpenROAD**: Physical design tool (inside container)
- **OpenSTA**: Static timing analysis (inside container)

## Safety Model

### Safety Domains

- **sandbox**: Exploratory, permissive (all ECO classes allowed)
- **guarded**: Default, production-like (restricted ECO classes, standard gates)
- **locked**: Conservative, regression-only (minimal changes, strict gates)

### ECO Classes by Blast Radius

- **topology_neutral**: Safe, no connectivity changes
- **placement_local**: Localized placement adjustments
- **routing_affecting**: May change routing topology
- **global_disruptive**: Large-scale changes, highest risk

Safety domains constrain which ECO classes are legal at each stage.

## Execution Model

1. **Controller layer** (Python) runs outside container
2. **Trial execution layer** runs OpenROAD/OpenSTA inside container
3. Each trial:
   - Executes in isolated working directory
   - Consumes immutable snapshot (read-only)
   - Emits structured artifacts
   - Is side-effect free

## Observability

### Ray Dashboard
- Cluster health and node status
- Running/completed trial tasks per stage
- Per-stage throughput, failures, resource utilization
- Deep links to trial artifacts

### Artifacts
- **Study-level**: summary, safety trace, Run Legality Report
- **Stage-level**: aggregated metrics, performance summaries
- **Trial-level**: timing reports, congestion reports, heatmaps, logs

### Telemetry Schema
- Study/Stage/Case indexed
- JSON format (machine-readable)
- Backward-compatible evolution
- Timestamps, provenance, metrics

## Reference Studies

Noodle 2 ships with baseline studies for each supported PDK:

- **nangate45_base**: Fast bring-up target
- **asap7_base**: High routing pressure, timing-driven
- **sky130_base**: OpenLane sky130A reference

### ASAP7-Specific Workarounds

ASAP7 requires explicit configuration workarounds:

```tcl
# Explicit routing layers
set_routing_layers -signal metal2-metal9 -clock metal6-metal9

# Explicit floorplan site
initialize_floorplan \
  -utilization 0.55 \
  -site asap7sc7p5t_28_R_24_NP_162NW_34O

# Pin placement on mid-stack metals
place_pins -random \
  -hor_layers {metal4} \
  -ver_layers {metal5}
```

**Memory anchor**: ASAP7 is "timing-driven, high-metal, low-utilization, STA-first."

## Common Tasks

### Start Ray Cluster

```bash
ray start --head --dashboard-host=0.0.0.0
# Dashboard: http://localhost:8265
```

### Stop Ray Cluster

```bash
ray stop
```

### Execute a Study (future)

```bash
python -m noodle2.controller run --study studies/nangate45_demo.yaml
```

### Generate Reports (future)

```bash
python -m noodle2.reports summary --study nangate45_demo
python -m noodle2.reports lineage --study nangate45_demo --format dot
```

## Development Notes

### Current Development Phase
This is **Session 1** of the implementation. The foundation is being established:
- ✅ Feature list created (205 features)
- ✅ Init script implemented
- ✅ README and project structure defined
- 🚧 Core controller logic (next priority)
- 🚧 Trial runner and parsers (next priority)

### Deferred Features (Workarounds Available)
- **Multi-node Ray**: Use single-node for development
- **Headless GUI (Xvfb)**: Use interactive X11 passthrough for heatmap exports
- **Reference snapshots**: Start with Nangate45, add ASAP7/Sky130 progressively

### Explicit Non-Goals
Noodle 2 intentionally does **not**:
- Invent ECOs (delegates to human or future AI)
- Replace OpenROAD algorithms
- Modify PD tool internals
- Rely on opaque optimization or ML
- Silently escalate risk

## Contributing

### Marking Features as Complete

When you complete a feature:

```python
# Load feature list
import json
with open('feature_list.json', 'r') as f:
    features = json.load(f)

# Find and mark feature as passing
for feature in features:
    if "Ray cluster" in feature['description']:
        feature['passes'] = True

# Save updated list
with open('feature_list.json', 'w') as f:
    json.dump(features, f, indent=2)
```

**Never remove features or edit descriptions/steps.** This ensures no functionality is missed.

### Commit Guidelines

- Commit frequently with descriptive messages
- Reference feature numbers when implementing features
- Run validation before committing (when tests exist)
- Include Co-Authored-By line for Claude assistance

## Resources

- **Full specification**: See `app_spec.txt` for complete product requirements
- **Feature list**: `feature_list.json` is the single source of truth for development
- **Ray documentation**: https://docs.ray.io/
- **OpenROAD documentation**: https://openroad.readthedocs.io/

## License

To be determined.

## Contact

To be determined.

---

**Remember**: Noodle 2 is not an optimizer. It is the control plane that makes optimization trustworthy at scale.
