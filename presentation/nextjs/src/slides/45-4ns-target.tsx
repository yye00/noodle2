import Slide from "@/components/Slide";

export default function Slide45() {
  return (
    <Slide>
      <h1>The 4ns Target: Is It Achievable?</h1>
      <p><strong>Context:</strong></p>
      <ul>
        <li>Original Microwatt design: 15ns clock (66 MHz) - meets timing</li>
        <li>Our aggressive target: 4ns clock (250 MHz) - severe violations</li>
      </ul>
      <p><strong>Analysis:</strong></p>
      <ul>
        <li>We&apos;re asking for <strong>3.75x speedup</strong> over the nominal design</li>
        <li>Final WNS: -1466ps means we&apos;re <strong>1.47ns short</strong> of the 4ns target</li>
        <li>Effective achievable clock: ~5.5ns (180 MHz)</li>
      </ul>
      <p>
        <strong>Conclusion:</strong> The 4ns target may be physically impossible
        for this design on Sky130. The remaining WNS represents a{" "}
        <strong>hard physical limit</strong>, not a failure of ECO optimization.
      </p>
    </Slide>
  );
}
