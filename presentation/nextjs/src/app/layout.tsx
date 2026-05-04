import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Noodle2 — Physical Design ECO Orchestration",
  description:
    "Case-study deck for Noodle2: automated timing closure via Ray-parallel ECO trials on real OpenROAD execution.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
