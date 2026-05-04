import Slide from "@/components/Slide";

export default function Slide02() {
  return (
    <Slide>
      <h1>What is Noodle2?</h1>
      <ul>
        <li><strong>ECO Orchestration System</strong> for physical design timing closure</li>
        <li>Automatically applies and evaluates <strong>Engineering Change Orders</strong></li>
        <li>Uses <strong>parallel execution</strong> with Ray for trial exploration</li>
        <li>Implements <strong>prior learning</strong> to avoid ineffective ECOs</li>
        <li>Supports <strong>checkpoint/rollback</strong> for robustness</li>
      </ul>
      <p>
        <em>
          All results shown are from <strong>REAL OpenROAD execution</strong> -
          no mocking or simulation
        </em>
      </p>
    </Slide>
  );
}
