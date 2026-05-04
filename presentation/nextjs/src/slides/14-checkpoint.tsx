import Slide from "@/components/Slide";

export default function Slide14() {
  return (
    <Slide>
      <h1>Checkpoint &amp; Rollback System</h1>
      <p><strong>How it works:</strong></p>
      <ul>
        <li>After each stage, compare current best WNS to historical best</li>
        <li>If degradation exceeds threshold, rollback to checkpoint</li>
      </ul>
      <p><strong>Configuration (from YAML):</strong></p>
      <pre><code>{`viability:
  enable_rollback: true
  rollback_threshold_ps: 200  # Trigger if WNS degrades > 200ps`}</code></pre>
      <p><strong>Behavior:</strong></p>
      <ul>
        <li><strong>&lt; threshold</strong>: Flag degradation (red in diagram), continue</li>
        <li><strong>&gt;= threshold</strong>: Rollback to best known state, retry from checkpoint</li>
      </ul>
    </Slide>
  );
}
