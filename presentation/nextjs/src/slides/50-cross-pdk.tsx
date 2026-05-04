import Slide from "@/components/Slide";

export default function Slide50() {
  return (
    <Slide>
      <h1>Cross-PDK Comparison</h1>
      <table>
        <thead>
          <tr>
            <th>PDK</th>
            <th>Design</th>
            <th>Cells</th>
            <th>WNS Impr.</th>
            <th>hot_ratio Red.</th>
            <th>Runtime</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>Nangate45</td><td>Ibex</td><td>~10K</td><td>+14.7%</td><td>-71.6%</td><td>1h 50m</td></tr>
          <tr><td>ASAP7</td><td>Ibex</td><td>~10K</td><td>+5.9%</td><td>-99.3%</td><td>2h 9m</td></tr>
          <tr>
            <td><strong>Sky130</strong></td>
            <td><strong>Microwatt</strong></td>
            <td><strong>162K</strong></td>
            <td><strong>+51.0%</strong></td>
            <td><strong>-99.7%</strong></td>
            <td><strong>2h 1m</strong></td>
          </tr>
        </tbody>
      </table>
      <p><strong>Pattern:</strong> hot_ratio reduction consistently &gt; WNS improvement</p>
      <ul>
        <li>ECOs effectively clean up most violations</li>
        <li>Worst path(s) have structural/physical limits</li>
      </ul>
    </Slide>
  );
}
