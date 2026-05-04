import Slide from "@/components/Slide";

export default function Slide54() {
  return (
    <Slide>
      <h1>Rollback System Summary</h1>
      <table>
        <thead>
          <tr><th>Parameter</th><th>Value</th><th>Purpose</th></tr>
        </thead>
        <tbody>
          <tr><td><code>enable_rollback</code></td><td>true</td><td>Activate rollback monitoring</td></tr>
          <tr><td><code>rollback_threshold_ps</code></td><td>200</td><td>Trigger if WNS degrades &gt; 200ps</td></tr>
        </tbody>
      </table>
      <p><strong>Sky130 Microwatt Results:</strong></p>
      <ul>
        <li>Degradation detected: Stage 6 (9ps regression)</li>
        <li>Rollback triggered: <strong>No</strong> (9ps &lt; 200ps threshold)</li>
        <li>Total rollbacks: 0</li>
      </ul>
      <p>
        <em>System correctly distinguished minor fluctuation from catastrophic regression</em>
      </p>
    </Slide>
  );
}
