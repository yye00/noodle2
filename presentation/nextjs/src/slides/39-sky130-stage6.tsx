import Slide from "@/components/Slide";

export default function Slide39() {
  return (
    <Slide>
      <h1>Stage 6: Degradation Analysis</h1>
      <p><strong>What happened at Stage 6?</strong></p>
      <table>
        <thead>
          <tr><th>Metric</th><th>Stage 5</th><th>Stage 6</th><th>Delta</th></tr>
        </thead>
        <tbody>
          <tr><td>Best WNS</td><td>-1457 ps</td><td>-1466 ps</td><td><strong>-9 ps</strong> (worse)</td></tr>
        </tbody>
      </table>
      <p><strong>Rollback decision:</strong></p>
      <ul>
        <li>Degradation: 9ps</li>
        <li>Threshold: 200ps (from YAML config)</li>
        <li><strong>9ps &lt; 200ps -&gt; No rollback triggered</strong></li>
      </ul>
      <p>
        <strong>Why no rollback?</strong> The 9ps regression was minor.
        Survivor selection may have chosen a variant with slightly worse WNS
        but better overall fitness (hot_ratio, area, etc.).
      </p>
    </Slide>
  );
}
