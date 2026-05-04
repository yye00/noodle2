import Slide from "@/components/Slide";

export default function Slide11() {
  return (
    <Slide>
      <h1>ORFS - OpenROAD Flow Scripts</h1>
      <p>
        <strong>OpenROAD-flow-scripts (ORFS)</strong> provides the build infrastructure:
      </p>
      <pre><code>{`# Build Microwatt for Sky130
make DESIGN_CONFIG=designs/sky130hd/microwatt/config.mk place`}</code></pre>
      <p><strong>Build Stages:</strong></p>
      <ol>
        <li><strong>Synthesis</strong> - Yosys RTL to netlist</li>
        <li><strong>Floorplanning</strong> - Die size, IO placement</li>
        <li><strong>Placement</strong> - Cell placement optimization</li>
        <li><strong>CTS</strong> - Clock tree synthesis</li>
        <li><strong>Routing</strong> - Global and detailed routing</li>
        <li><strong>Finishing</strong> - DRC, LVS, timing signoff</li>
      </ol>
      <p>
        <strong>Noodle2 starts post-placement</strong> - takes ODB snapshot and applies ECOs
      </p>
    </Slide>
  );
}
