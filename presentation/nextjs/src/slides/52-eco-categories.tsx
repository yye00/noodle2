import Slide from "@/components/Slide";

export default function Slide52() {
  return (
    <Slide>
      <h1>ECO Success Rates by Category</h1>
      <table>
        <thead>
          <tr><th>Category</th><th>ECOs</th><th>Success Rate</th></tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Repair</strong></td>
            <td>hold_repair, sequential_repair, repair_design, tie_fanout_repair</td>
            <td><strong>100%</strong></td>
          </tr>
          <tr>
            <td><strong>Timing</strong></td>
            <td>aggressive_timing, multi_pass_timing, full_optimization</td>
            <td><strong>100%</strong></td>
          </tr>
          <tr>
            <td><strong>Cell</strong></td>
            <td>cell_resize, cell_swap, buffer_insertion, buffer_removal</td>
            <td><strong>100%</strong></td>
          </tr>
          <tr>
            <td><strong>Placement</strong></td>
            <td>timing_driven_placement, placement_density, iterative_timing_driven</td>
            <td><strong>100%</strong></td>
          </tr>
          <tr>
            <td><strong>Failed</strong></td>
            <td>gate_cloning, dead_logic_elimination</td>
            <td><strong>0%</strong></td>
          </tr>
          <tr>
            <td><strong>PDK-Dependent</strong></td>
            <td>clock_net_repair</td>
            <td>68.3% (failed on Sky130)</td>
          </tr>
        </tbody>
      </table>
    </Slide>
  );
}
