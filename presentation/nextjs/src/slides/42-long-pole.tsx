import Slide from "@/components/Slide";

export default function Slide42() {
  return (
    <Slide>
      <h1>The &quot;Long Pole in the Tent&quot; Problem</h1>
      <p>
        <strong>Observation:</strong> hot_ratio improved 99.7% but WNS only improved 51%
      </p>
      <table>
        <thead>
          <tr><th>Metric</th><th>Definition</th><th>Change</th></tr>
        </thead>
        <tbody>
          <tr><td><strong>hot_ratio</strong></td><td>Fraction of paths violating timing</td><td>9.7% -&gt; 0.03%</td></tr>
          <tr><td><strong>WNS</strong></td><td>Worst single path&apos;s negative slack</td><td>-2989ps -&gt; -1466ps</td></tr>
        </tbody>
      </table>
      <p><strong>What this means:</strong></p>
      <ul>
        <li>We fixed <strong>99.7% of all timing violations</strong></li>
        <li>But the <strong>single worst path</strong> only improved 51%</li>
        <li>Almost all paths are now clean; ONE stubborn path dominates WNS</li>
      </ul>
    </Slide>
  );
}
