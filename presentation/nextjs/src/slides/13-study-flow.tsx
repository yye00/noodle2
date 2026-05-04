import Slide from "@/components/Slide";

export default function Slide13() {
  return (
    <Slide>
      <h1>Study Execution Flow</h1>
      <ol>
        <li><strong>Base Case Verification</strong> - Validate initial design metrics</li>
        <li><strong>Stage Execution</strong> - 20 stages with 25 trials each</li>
        <li><strong>Survivor Selection</strong> - Keep best performing variants</li>
        <li><strong>Prior Learning</strong> - Track ECO effectiveness</li>
        <li><strong>Checkpoint/Rollback</strong> - Save state, recover from degradation</li>
        <li><strong>Visualization</strong> - Generate heatmaps, trajectories, summaries</li>
      </ol>
      <p>
        <strong>Total: 500 trials per study with parallel Ray execution</strong>
      </p>
    </Slide>
  );
}
