import Slide from "@/components/Slide";

export default function Slide44() {
  return (
    <Slide>
      <h1>Are We Missing Something?</h1>
      <p><strong>What Noodle2 ECOs can do:</strong></p>
      <ul>
        <li>Cell resizing (faster/slower cells)</li>
        <li>Buffer insertion/removal</li>
        <li>Timing-driven placement optimization</li>
        <li>Gate cloning for fanout</li>
      </ul>
      <p><strong>What might be needed for the worst path:</strong></p>
      <ul>
        <li><strong>Path-specific targeting</strong> - Focus ECOs on the critical path</li>
        <li><strong>Logic restructuring</strong> - Retiming, pipelining (requires RTL changes)</li>
        <li><strong>Placement constraints</strong> - Manual floorplanning of critical cells</li>
        <li><strong>Accept physical limits</strong> - 4ns (250MHz) may be beyond Sky130 capability</li>
      </ul>
    </Slide>
  );
}
