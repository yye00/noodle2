import Slide from "@/components/Slide";

export default function Slide32() {
  return (
    <Slide>
      <h1>Sky130 Microwatt - Design Setup</h1>
      <table>
        <thead>
          <tr><th>Property</th><th>Value</th></tr>
        </thead>
        <tbody>
          <tr><td>PDK</td><td>Sky130HD (130nm open-source)</td></tr>
          <tr><td>Design</td><td><strong>Microwatt OpenPOWER Core</strong></td></tr>
          <tr><td>Cell Count</td><td><strong>162,637 cells</strong></td></tr>
          <tr><td>Clock Period</td><td>4ns (250 MHz - aggressive)</td></tr>
          <tr><td>ODB Size</td><td>95 MB</td></tr>
        </tbody>
      </table>
      <p>
        <strong>16x larger than Ibex!</strong> Full OpenPOWER implementation.
      </p>
    </Slide>
  );
}
