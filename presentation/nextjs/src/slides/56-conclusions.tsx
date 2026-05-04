import Slide from "@/components/Slide";

export default function Slide56() {
  return (
    <Slide>
      <h1>Conclusions</h1>
      <ul>
        <li>Noodle2 successfully improved timing on <strong>3 different PDKs</strong></li>
        <li>
          <strong>162K cell Microwatt</strong> achieved 51% WNS improvement,{" "}
          <strong>99.7% violation reduction</strong>
        </li>
        <li>All executions used <strong>real OpenROAD</strong> - no simulation</li>
        <li>Prior learning effectively filters ineffective ECOs</li>
        <li>System scales from 10K to 160K+ cells</li>
        <li>
          <strong>Key insight:</strong> ECOs excel at fixing most violations;
          worst path(s) may require architectural changes
        </li>
      </ul>
      <h3>Total: 1,500 real ECO trials executed</h3>
    </Slide>
  );
}
