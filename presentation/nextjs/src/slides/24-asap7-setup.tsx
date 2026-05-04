import Slide from "@/components/Slide";

export default function Slide24() {
  return (
    <Slide>
      <h1>ASAP7 - Design Setup</h1>
      <table>
        <thead>
          <tr><th>Property</th><th>Value</th></tr>
        </thead>
        <tbody>
          <tr><td>PDK</td><td>ASAP7 (7nm predictive)</td></tr>
          <tr><td>Design</td><td>Ibex RISC-V Core</td></tr>
          <tr><td>Cell Count</td><td>~10,000 cells</td></tr>
          <tr><td>Clock Period</td><td>Aggressive (7nm timing)</td></tr>
          <tr><td>ODB Size</td><td>~10 MB</td></tr>
        </tbody>
      </table>
      <p>
        <strong>Extreme Case Generation:</strong> Same Ibex core mapped to
        advanced 7nm node. Smaller feature size = tighter timing margins =
        harder closure.
      </p>
    </Slide>
  );
}
