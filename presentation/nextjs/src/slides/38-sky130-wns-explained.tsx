import Slide from "@/components/Slide";

export default function Slide38() {
  return (
    <Slide>
      <h1>Understanding the WNS Trajectory</h1>
      <p><strong>Why does WNS stay flat, then jump, then flatten again?</strong></p>
      <table>
        <thead>
          <tr><th>Stage</th><th>Best WNS</th><th>What Happened</th></tr>
        </thead>
        <tbody>
          <tr><td>0-&gt;1</td><td>-2818 -&gt; -1892</td><td>cell_resize + buffer_insertion unlocked improvement</td></tr>
          <tr><td>1-&gt;3</td><td>-1892 -&gt; -1466</td><td>multi_pass_timing found better optimum</td></tr>
          <tr><td>4-&gt;19</td><td>-1466</td><td>Hit local minimum - no ECO could improve further</td></tr>
        </tbody>
      </table>
      <p>
        <strong>Key insight:</strong> Timing optimization is non-linear. Most
        ECOs provide marginal gains; occasionally one &quot;unlocks&quot; a new
        local optimum.
      </p>
    </Slide>
  );
}
