import Slide from "@/components/Slide";

export default function Slide34() {
  return (
    <Slide>
      <h1>Sky130 Microwatt - Initial State (Broken)</h1>
      <table>
        <thead>
          <tr><th>Metric</th><th>Value</th><th>Status</th></tr>
        </thead>
        <tbody>
          <tr><td><strong>WNS</strong></td><td>-2989 ps</td><td>Nearly 3ns negative slack!</td></tr>
          <tr><td><strong>hot_ratio</strong></td><td>0.097</td><td>~10% paths violated</td></tr>
        </tbody>
      </table>
    </Slide>
  );
}
