"use client";

import { useCallback, useEffect, useState } from "react";
import { slides } from "@/slides";
import styles from "@/styles/deck.module.css";

function readHashIndex(total: number): number {
  if (typeof window === "undefined") return 0;
  const raw = window.location.hash.replace(/^#\/?/, "");
  const n = parseInt(raw, 10);
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(total - 1, n - 1));
}

export default function Deck() {
  const total = slides.length;
  const [index, setIndex] = useState(0);

  useEffect(() => {
    setIndex(readHashIndex(total));
    const onHash = () => setIndex(readHashIndex(total));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [total]);

  const go = useCallback(
    (next: number) => {
      const clamped = Math.max(0, Math.min(total - 1, next));
      setIndex(clamped);
      if (typeof window !== "undefined") {
        window.location.hash = String(clamped + 1);
      }
    },
    [total],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      switch (e.key) {
        case "ArrowRight":
        case "PageDown":
        case " ":
          e.preventDefault();
          go(index + 1);
          break;
        case "ArrowLeft":
        case "PageUp":
          e.preventDefault();
          go(index - 1);
          break;
        case "Home":
          e.preventDefault();
          go(0);
          break;
        case "End":
          e.preventDefault();
          go(total - 1);
          break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, index, total]);

  const Current = slides[index];

  return (
    <div className={styles.deck}>
      <div className={styles.stage}>
        <Current />
      </div>
      <div className={styles.footer}>
        <div>
          <button onClick={() => go(index - 1)} disabled={index === 0}>
            ← Prev
          </button>
          <button onClick={() => go(index + 1)} disabled={index === total - 1}>
            Next →
          </button>
        </div>
        <div>
          {index + 1} / {total}
        </div>
      </div>
    </div>
  );
}
