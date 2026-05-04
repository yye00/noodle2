import Slide from "@/components/Slide";

export default function Slide35() {
  return (
    <Slide>
      <h1>Sky130 Microwatt - Stage Progression</h1>
      <img src="/images/sky130/stage_progression.png" alt="Sky130 stage progression" />
      <p>
        20 stages, 500 trials. <strong>Stage 6 (red):</strong> degradation
        detected but below rollback threshold.
      </p>
    </Slide>
  );
}
