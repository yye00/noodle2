import Slide from "@/components/Slide";

export default function Slide03() {
  return (
    <Slide>
      <h1>Technology Stack</h1>
      <table>
        <thead>
          <tr>
            <th>Layer</th>
            <th>Technology</th>
            <th>Purpose</th>
          </tr>
        </thead>
        <tbody>
          <tr><td><strong>Orchestration</strong></td><td>Noodle2 (Python)</td><td>ECO selection, prior learning</td></tr>
          <tr><td><strong>Parallelism</strong></td><td>Ray</td><td>Distributed execution</td></tr>
          <tr><td><strong>EDA Engine</strong></td><td>OpenROAD</td><td>Timing analysis, ECO application</td></tr>
          <tr><td><strong>Build Flow</strong></td><td>ORFS</td><td>Synthesis, placement, routing</td></tr>
          <tr><td><strong>PDKs</strong></td><td>Nangate45, ASAP7, Sky130</td><td>Process design kits</td></tr>
          <tr><td><strong>Visualization</strong></td><td>Matplotlib</td><td>Heatmaps, trajectories</td></tr>
        </tbody>
      </table>
    </Slide>
  );
}
