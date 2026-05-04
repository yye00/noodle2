import Slide from "@/components/Slide";

export default function Slide43() {
  return (
    <Slide>
      <h1>Why Does the Worst Path Resist Improvement?</h1>
      <p><strong>The worst path likely has fundamental constraints:</strong></p>
      <ol>
        <li><strong>Long combinational depth</strong> - Many logic stages in series</li>
        <li><strong>Placement-limited</strong> - Cells physically far apart, wire delay dominates</li>
        <li><strong>Technology limits</strong> - Already using maximum drive strength cells</li>
        <li><strong>Critical logic</strong> - Carry chains, multipliers, barrel shifters</li>
        <li><strong>Routing congestion</strong> - Detours adding wire delay</li>
      </ol>
      <p>
        <strong>
          ECOs are effective at fixing &quot;moderately bad&quot; paths but struggle
          with the &quot;truly terrible&quot; path(s).
        </strong>
      </p>
    </Slide>
  );
}
