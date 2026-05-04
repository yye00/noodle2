import Slide from "@/components/Slide";

export default function Slide12() {
  return (
    <Slide>
      <h1>ECO Types Supported</h1>
      <table>
        <thead>
          <tr>
            <th>Category</th>
            <th>ECOs</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Topology Neutral</strong></td>
            <td>Cell Resize, Buffer Insertion/Removal, Pin Swap, Gate Cloning</td>
          </tr>
          <tr>
            <td><strong>Placement Affecting</strong></td>
            <td>Timing-Driven Placement, Placement Density, Iterative Optimization</td>
          </tr>
          <tr>
            <td><strong>Global/Aggressive</strong></td>
            <td>Full Optimization, Multi-Pass Timing, VT Swap</td>
          </tr>
          <tr>
            <td><strong>Repair</strong></td>
            <td>Hold Repair, Clock Net Repair, Tie Fanout Repair</td>
          </tr>
        </tbody>
      </table>
    </Slide>
  );
}
