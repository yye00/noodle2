import Slide from "@/components/Slide";

export default function Slide47() {
  return (
    <Slide>
      <h1>Sky130 Microwatt - Final Results</h1>
      <table>
        <thead>
          <tr><th>Metric</th><th>Initial</th><th>Final</th><th>Improvement</th></tr>
        </thead>
        <tbody>
          <tr><td><strong>WNS</strong></td><td>-2989 ps</td><td>-1466 ps</td><td><strong>+51.0%</strong></td></tr>
          <tr><td><strong>hot_ratio</strong></td><td>0.097</td><td>0.0003</td><td><strong>-99.7%</strong></td></tr>
        </tbody>
      </table>
      <p><strong>Execution:</strong> 20 stages, 500 trials, 2hr 1min runtime</p>
      <h3>Key Achievement: 99.7% of timing violations eliminated</h3>
    </Slide>
  );
}
