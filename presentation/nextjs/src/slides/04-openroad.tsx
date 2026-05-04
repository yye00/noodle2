import Slide from "@/components/Slide";

export default function Slide04() {
  return (
    <Slide>
      <h1>OpenROAD - The EDA Engine</h1>
      <p>
        <strong>OpenROAD</strong> is an open-source RTL-to-GDS flow for digital design:
      </p>
      <ul>
        <li><strong>OpenSTA</strong> - Static Timing Analysis (WNS, TNS, hot_ratio)</li>
        <li><strong>TritonPlace</strong> - Global and detailed placement</li>
        <li><strong>FastRoute</strong> - Global routing</li>
        <li><strong>TritonRoute</strong> - Detailed routing</li>
        <li><strong>ReSizer</strong> - Gate sizing, buffer insertion</li>
      </ul>
      <p><strong>Why OpenROAD?</strong></p>
      <ul>
        <li>Production-quality timing analysis</li>
        <li>Real ECO commands (resize, buffer, repair)</li>
        <li>Reproducible, scriptable, open-source</li>
      </ul>
    </Slide>
  );
}
