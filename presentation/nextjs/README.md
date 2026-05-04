# Noodle2 Presentation (Next.js)

Minimal Next.js port of `presentation/noodle2_results.md` for hand-off to a
styling agent that will reapply the master-deck visual system.

## Run

```bash
npm install
npm run dev      # http://localhost:3000
```

## Navigation

- ←  /  PageUp        previous slide
- →  /  Space  /  PageDown   next slide
- Home / End          first / last
- URL hash (`#3`) persists current slide

## Structure

- `src/slides/NN-name.tsx` — one component per slide, in order.
- `src/slides/index.ts` — ordered array consumed by `<Deck>`.
- `src/components/Deck.tsx` — keyboard nav + hash routing.
- `src/components/Slide.tsx` — content wrapper.
- `src/styles/deck.module.css` — layout-only CSS (no theme).
- `public/images/` — chart and dashboard PNGs.

Content is intentionally unstyled. Any visual polish is done by the next agent.
