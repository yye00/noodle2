import Slide from "@/components/Slide";

export default function Slide57() {
  return (
    <Slide>
      <h1>How This Was Built</h1>
      <p>
        The Noodle2 codebase was generated using <strong>bob3.1</strong>, an
        autonomous code-generation framework that orchestrates the design,
        implementation, and validation of multi-module software systems.
      </p>
      <ul>
        <li>
          <strong>Source generator:</strong> bob3.1 (
          <code>/home/captain/work/bob/bob3.1/</code>)
        </li>
        <li>
          <strong>Output:</strong> Noodle2 — Python orchestrator, Ray-based
          trial runner, OpenROAD ECO dispatch, prior-learning tracker,
          checkpoint/rollback subsystem, visualization pipeline
        </li>
        <li>
          <strong>Verification:</strong> all results in this deck come from real
          OpenROAD execution against the generated codebase, not simulation
        </li>
      </ul>
      <p>
        <em>
          The case study you just walked through is the empirical evidence that
          bob3.1-generated code holds up under production-quality EDA workloads.
        </em>
      </p>
    </Slide>
  );
}
