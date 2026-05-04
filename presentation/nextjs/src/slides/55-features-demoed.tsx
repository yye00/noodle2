import Slide from "@/components/Slide";

export default function Slide55() {
  return (
    <Slide>
      <h1>Key Noodle2 Features Demonstrated</h1>
      <ul>
        <li><strong>Parallel Execution</strong> - Ray-based trial parallelism</li>
        <li><strong>Prior Learning</strong> - ECO effectiveness tracking</li>
        <li><strong>Checkpoint/Rollback</strong> - Recovery from degradation (threshold: 200ps)</li>
        <li><strong>Degradation Detection</strong> - Stage 6 flagged without rollback</li>
        <li><strong>Multi-PDK Support</strong> - Nangate45, ASAP7, Sky130</li>
        <li><strong>Safety Domains</strong> - Sandbox, guarded, locked modes</li>
      </ul>
    </Slide>
  );
}
