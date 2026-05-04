import Slide from "@/components/Slide";

export default function Slide30() {
  return (
    <Slide>
      <h1>ASAP7 - Final Results</h1>
      <table>
        <thead>
          <tr><th>Metric</th><th>Initial</th><th>Final</th><th>Improvement</th></tr>
        </thead>
        <tbody>
          <tr><td><strong>WNS</strong></td><td>-1067 ps</td><td>-1004 ps</td><td><strong>+5.9%</strong></td></tr>
          <tr><td><strong>hot_ratio</strong></td><td>0.55</td><td>0.004</td><td><strong>-99.3%</strong></td></tr>
        </tbody>
      </table>
      <p><strong>Execution:</strong> 20 stages, 500 trials, 2hr 9min runtime</p>
      <p><em>Excellent hot_ratio reduction despite modest WNS improvement</em></p>
    </Slide>
  );
}
