# Noodle2 Next.js Slide Deck — Design

**Date:** 2026-05-04
**Owner:** Yaakoub Elkhamra
**Status:** Approved (terminal-only brainstorm; user requested ship-asap)

## Goal

Port the existing Marp slide deck at `presentation/noodle2_results.md` into a
minimal Next.js application so it can be handed off to another agent that will
re-apply a master-deck visual style. The intermediate output is a content
carrier, not a presentation in its own right.

## Constraints

- **Slide-deck shape.** One slide on screen at a time, ←/→ keyboard navigation.
- **Content unchanged.** All 58 slides from the Marp source are ported verbatim
  (headings, bullets, tables, ASCII diagrams, image references). One additional
  slide is added at the end of the body content as a bob3.1 attribution.
- **No theme work.** Black text on white, default fonts, no transitions. The
  next agent re-styles to match the master deck.
- **No real source code in slides.** Audience is general software engineers.
  Concept-level prose only.
- **Minimal dependencies.** Next.js + React + TypeScript. No MDX, no Tailwind,
  no reveal.js, no animation libraries, no UI kits.

## Location

```
presentation/nextjs/
```

Sibling of `presentation/bundle/` and `presentation/generate_pptx.py`.

## File Layout

```
presentation/nextjs/
├── package.json
├── next.config.ts
├── tsconfig.json
├── .gitignore
├── public/
│   └── images/
│       ├── ray/{ray_overview,ray_jobs,ray_cluster,ray_metrics}.png
│       ├── nangate45/*.png
│       ├── asap7/*.png
│       └── sky130/*.png
└── src/
    ├── app/
    │   ├── layout.tsx
    │   └── page.tsx
    ├── components/
    │   ├── Deck.tsx
    │   └── Slide.tsx
    ├── slides/
    │   ├── index.ts                 (ordered array of slide components)
    │   └── 01-title.tsx ... 59-appendix.tsx
    └── styles/
        └── deck.module.css
```

## Slide Inventory (59 total)

The order matches `noodle2_results.md` 1:1, with the bob3.1 credit inserted
between "Conclusions" and "Thank You":

1.  Title
2.  What is Noodle2?
3.  Technology Stack
4.  OpenROAD - The EDA Engine
5.  Ray - Distributed Parallel Execution
6.  Ray Architecture for Noodle2
7.  Ray Dashboard - Overview
8.  Ray Dashboard - Jobs
9.  Ray Dashboard - Cluster Resources
10. Ray Dashboard - Metrics
11. ORFS - OpenROAD Flow Scripts
12. ECO Types Supported
13. Study Execution Flow
14. Checkpoint & Rollback System
15. Nangate45 (section divider)
16. Nangate45 - Design Setup
17. Nangate45 - Initial State
18. Nangate45 - Stage Progression
19. Nangate45 - WNS Trajectory
20. Nangate45 - Hot Ratio Trajectory
21. Nangate45 - Congestion Improvement
22. Nangate45 - Final Results
23. ASAP7 (section divider)
24. ASAP7 - Design Setup
25. ASAP7 - Initial State
26. ASAP7 - Stage Progression
27. ASAP7 - WNS Trajectory
28. ASAP7 - Hot Ratio Trajectory
29. ASAP7 - Congestion Improvement
30. ASAP7 - Final Results
31. Sky130 + Microwatt (section divider)
32. Sky130 Microwatt - Design Setup
33. Sky130 - Extreme Case Generation
34. Sky130 Microwatt - Initial State
35. Sky130 Microwatt - Stage Progression
36. Understanding the Stage Progression
37. Sky130 Microwatt - WNS Trajectory
38. Understanding the WNS Trajectory
39. Stage 6: Degradation Analysis
40. Sky130 Microwatt - Hot Ratio Trajectory
41. Critical Analysis (section divider)
42. The "Long Pole in the Tent" Problem
43. Why Does the Worst Path Resist Improvement?
44. Are We Missing Something?
45. The 4ns Target: Is It Achievable?
46. Sky130 Microwatt - Congestion Improvement
47. Sky130 Microwatt - Final Results
48. Timing Endpoint Statistics
49. Results Comparison (section divider)
50. Cross-PDK Comparison
51. ECO Effectiveness Leaderboard (All PDKs)
52. ECO Success Rates by Category
53. Why Did Some ECOs Fail?
54. Rollback System Summary
55. Key Noodle2 Features Demonstrated
56. Conclusions
57. **How This Was Built** (bob3.1 credit — *new*)
58. Thank You
59. Appendix: Heatmap Visualization Notes

## Component Sketch

### `Deck.tsx`
- Client component (`'use client'`).
- Holds `[index, setIndex]`.
- `useEffect` registers `keydown`: ←/PageUp → prev, →/Space/PageDown → next,
  Home → 0, End → last.
- Reads/writes `window.location.hash` to persist position.
- Renders `slides[index]` plus a tiny footer: `index + 1 / total` and ←/→ buttons.

### `Slide.tsx`
- Plain wrapper: `<section className={...}>{children}</section>`.
- Centers content with a max width.

### `slides/NN-name.tsx`
- Default-exports a React functional component returning JSX.
- Each slide's body mirrors its Marp markdown 1:1.

### `slides/index.ts`
- `export const slides = [Slide01, Slide02, …]` in render order.

## Image Handling

Copy `presentation/bundle/images/**` → `presentation/nextjs/public/images/**`
and reference them as `<img src="/images/sky130/wns_trajectory.png" />`.
(Plain `<img>`, not `next/image`, to avoid asset-config friction.)

## Out of Scope

Themes, transitions, speaker notes, PDF export, print layout, mobile layout,
dark mode, slide numbering badges beyond `n / total`, progress bar, MDX,
`next/image` optimization, Tailwind, ESLint config, tests.

## Build / Run

- `cd presentation/nextjs && npm install`
- `npm run dev` → `http://localhost:3000`
- `npm run build && npm run start` for production preview.

## Repository Hygiene

- `.gitignore` at repo root gains `.superpowers/` (brainstorming artifacts).
- Single commit on `main`, then push to `origin/main`.

## Hand-off

The next agent restyles to the master-deck visual system. Slide order, content,
and image positions are stable contracts; visual styling is theirs to define.
