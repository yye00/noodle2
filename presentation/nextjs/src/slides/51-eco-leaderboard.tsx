import Slide from "@/components/Slide";

export default function Slide51() {
  return (
    <Slide>
      <h1>ECO Effectiveness Leaderboard (All PDKs)</h1>
      <table>
        <thead>
          <tr>
            <th>ECO</th>
            <th>Applications</th>
            <th>Success</th>
            <th>Rate</th>
            <th>Prior Status</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>hold_repair</td><td>101</td><td>101</td><td><strong>100%</strong></td><td>good</td></tr>
          <tr><td>aggressive_timing</td><td>99</td><td>99</td><td><strong>100%</strong></td><td>good</td></tr>
          <tr><td>multi_pass_timing</td><td>97</td><td>97</td><td><strong>100%</strong></td><td>good</td></tr>
          <tr><td>sequential_repair</td><td>93</td><td>93</td><td><strong>100%</strong></td><td>good</td></tr>
          <tr><td>buffer_insertion</td><td>77</td><td>77</td><td><strong>100%</strong></td><td>good</td></tr>
          <tr><td><strong>gate_cloning</strong></td><td>76</td><td>0</td><td><strong>0%</strong></td><td>suspicious</td></tr>
          <tr><td>cell_resize</td><td>73</td><td>73</td><td><strong>100%</strong></td><td>good</td></tr>
          <tr><td><strong>dead_logic_elimination</strong></td><td>72</td><td>0</td><td><strong>0%</strong></td><td>suspicious</td></tr>
        </tbody>
      </table>
      <p><em>Total: 1,500 ECO applications across 3 PDKs</em></p>
    </Slide>
  );
}
