import type { ReactNode } from "react";
import styles from "@/styles/deck.module.css";

export default function Slide({
  children,
  lead = false,
}: {
  children: ReactNode;
  lead?: boolean;
}) {
  return (
    <section className={`${styles.slide}${lead ? " " + styles.lead : ""}`}>
      {children}
    </section>
  );
}
