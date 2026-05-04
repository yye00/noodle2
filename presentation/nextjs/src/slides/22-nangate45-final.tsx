import Slide from "@/components/Slide";

export default function Slide22() {
  return (
    <Slide>
      <h1>Nangate45 - Final Results</h1>
      <table>
        <thead>
          <tr><th>Metric</th><th>Initial</th><th>Final</th><th>Improvement</th></tr>
        </thead>
        <tbody>
          <tr><td><strong>WNS</strong></td><td>-1848 ps</td><td>-1576 ps</td><td><strong>+14.7%</strong></td></tr>
          <tr><td><strong>hot_ratio</strong></td><td>0.523</td><td>0.149</td><td><strong>-71.6%</strong></td></tr>
        </tbody>
      </table>
      <p><strong>Execution:</strong> 20 stages, 500 trials, 1hr 50min runtime</p>
    </Slide>
  );
}
