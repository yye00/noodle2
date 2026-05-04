import Slide from "@/components/Slide";

export default function Slide25() {
  return (
    <Slide>
      <h1>ASAP7 - Initial State (Broken)</h1>
      <table>
        <thead>
          <tr><th>Metric</th><th>Value</th><th>Status</th></tr>
        </thead>
        <tbody>
          <tr><td><strong>WNS</strong></td><td>-1067 ps</td><td>Setup violations at 7nm</td></tr>
          <tr><td><strong>hot_ratio</strong></td><td>0.55</td><td>55% of paths violated</td></tr>
        </tbody>
      </table>
    </Slide>
  );
}
