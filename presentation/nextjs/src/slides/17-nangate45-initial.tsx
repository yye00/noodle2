import Slide from "@/components/Slide";

export default function Slide17() {
  return (
    <Slide>
      <h1>Nangate45 - Initial State (Broken)</h1>
      <table>
        <thead>
          <tr><th>Metric</th><th>Value</th><th>Status</th></tr>
        </thead>
        <tbody>
          <tr><td><strong>WNS</strong></td><td>-1848 ps</td><td>Severe setup violations</td></tr>
          <tr><td><strong>hot_ratio</strong></td><td>0.523</td><td>52% of paths violated</td></tr>
        </tbody>
      </table>
    </Slide>
  );
}
