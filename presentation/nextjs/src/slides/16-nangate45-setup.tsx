import Slide from "@/components/Slide";

export default function Slide16() {
  return (
    <Slide>
      <h1>Nangate45 - Design Setup</h1>
      <table>
        <thead>
          <tr><th>Property</th><th>Value</th></tr>
        </thead>
        <tbody>
          <tr><td>PDK</td><td>Nangate45 (45nm)</td></tr>
          <tr><td>Design</td><td>Ibex RISC-V Core</td></tr>
          <tr><td>Cell Count</td><td>~10,000 cells</td></tr>
          <tr><td>Clock Period</td><td>Aggressive (tight constraints)</td></tr>
          <tr><td>ODB Size</td><td>8.3 MB</td></tr>
        </tbody>
      </table>
      <p>
        <strong>Extreme Case Generation:</strong> Applied aggressive clock
        constraints to production-realistic Ibex RISC-V core, creating severe
        setup timing violations.
      </p>
    </Slide>
  );
}
