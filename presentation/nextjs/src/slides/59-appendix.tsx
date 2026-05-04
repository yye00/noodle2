import Slide from "@/components/Slide";

export default function Slide59() {
  return (
    <Slide>
      <h1>Appendix: Heatmap Visualization Notes</h1>
      <p><strong>Current resolution:</strong> 40x40 normalized grid</p>
      <p>
        <strong>Limitation:</strong> Heatmaps are exported from OpenROAD&apos;s{" "}
        <code>gui::dump_heatmap</code> without coordinate bounds, so true-to-floorplan
        aspect ratios are not preserved.
      </p>
      <p><strong>Future improvement:</strong> Export heatmaps in bbox format (x0,y0,x1,y1,value) to enable:</p>
      <ul>
        <li>True-scale rendering with correct aspect ratio</li>
        <li>Micron-accurate coordinate display</li>
        <li>Higher resolution spatial analysis</li>
      </ul>
    </Slide>
  );
}
