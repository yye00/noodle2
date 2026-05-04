import Slide from "@/components/Slide";

export default function Slide48() {
  return (
    <Slide>
      <h1>Timing Endpoint Statistics</h1>
      <table>
        <thead>
          <tr>
            <th>Design</th>
            <th>Cells</th>
            <th>Initial Violating</th>
            <th>Final Violating</th>
            <th><strong>Endpoints Fixed</strong></th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Sky130 Microwatt</strong></td>
            <td>162K</td>
            <td>~6,467</td>
            <td>~20</td>
            <td><strong>6,447 (99.7%)</strong></td>
          </tr>
          <tr>
            <td><strong>ASAP7 Ibex</strong></td>
            <td>~10K</td>
            <td>~2,039</td>
            <td>~15</td>
            <td><strong>2,024 (99.3%)</strong></td>
          </tr>
          <tr>
            <td><strong>Nangate45 Ibex</strong></td>
            <td>~10K</td>
            <td>~3,580</td>
            <td>~1,020</td>
            <td><strong>2,560 (71.5%)</strong></td>
          </tr>
        </tbody>
      </table>
      <p>
        <strong>Key Insight:</strong> ECOs successfully eliminated thousands of
        timing violations across all PDKs.
      </p>
      <p><em>Endpoint counts extracted from OpenROAD RSZ-0094 logs</em></p>
    </Slide>
  );
}
