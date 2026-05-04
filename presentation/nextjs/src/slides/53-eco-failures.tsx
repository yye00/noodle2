import Slide from "@/components/Slide";

export default function Slide53() {
  return (
    <Slide>
      <h1>Why Did Some ECOs Fail?</h1>
      <p><strong>gate_cloning (0% success, 76 attempts):</strong></p>
      <ul>
        <li>Intended for high-fanout nets</li>
        <li>May not have found suitable candidates</li>
        <li>Or cloning didn&apos;t improve timing on critical paths</li>
      </ul>
      <p><strong>dead_logic_elimination (0% success, 72 attempts):</strong></p>
      <ul>
        <li>No dead logic found in these optimized designs</li>
        <li>Designs already clean from synthesis</li>
      </ul>
      <p><strong>clock_net_repair (68.3% success):</strong></p>
      <ul>
        <li>100% success on Nangate45, ASAP7</li>
        <li>0% success on Sky130 - different clock tree structure</li>
      </ul>
      <p>
        <em>
          Prior learning correctly identified these as &quot;suspicious&quot;
          and deprioritized them
        </em>
      </p>
    </Slide>
  );
}
