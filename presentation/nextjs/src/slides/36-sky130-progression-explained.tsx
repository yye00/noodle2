import Slide from "@/components/Slide";

export default function Slide36() {
  return (
    <Slide>
      <h1>Understanding the Stage Progression</h1>
      <p><strong>Legend:</strong></p>
      <ul>
        <li><strong>Blue boxes</strong>: Normal stages - WNS improved or stayed same</li>
        <li><strong>Red boxes</strong>: Degradation stages - WNS got worse vs previous stage</li>
        <li><strong>Green box</strong>: Winner stage - final best result</li>
      </ul>
      <p><strong>Each box shows:</strong></p>
      <ul>
        <li>Stage number (S0-S19)</li>
        <li>Trials executed (25 per stage)</li>
        <li>Survivors selected (funnel: 8 -&gt; 6 -&gt; 4 -&gt; 3 -&gt; 2)</li>
        <li>Delta WNS from previous stage</li>
        <li>Top 2 ECOs used</li>
      </ul>
    </Slide>
  );
}
