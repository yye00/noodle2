import Slide from "@/components/Slide";

export default function Slide33() {
  return (
    <Slide>
      <h1>Sky130 - Extreme Case Generation</h1>
      <ol>
        <li><strong>Built Microwatt</strong> using OpenROAD-flow-scripts</li>
        <li><strong>Ran synthesis -&gt; placement</strong> (47 min ORFS build)</li>
        <li><strong>Applied aggressive 4ns clock</strong> (vs 15ns nominal)</li>
        <li><strong>Created severe timing violations</strong> for ECO demo</li>
      </ol>
      <table>
        <thead>
          <tr><th>Clock</th><th>Frequency</th><th>Status</th></tr>
        </thead>
        <tbody>
          <tr><td>Original</td><td>15ns (66 MHz)</td><td>Meets timing</td></tr>
          <tr><td>Demo</td><td>4ns (250 MHz)</td><td>Severe violations</td></tr>
        </tbody>
      </table>
    </Slide>
  );
}
