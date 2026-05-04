import Slide from "@/components/Slide";

const diagram = `\
┌─────────────────────────────────────────────────────────────┐
│                     RAY HEAD NODE                           │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ Study Executor  │  │ Ray Dashboard   │                  │
│  │ (Orchestrator)  │  │ (Monitoring)    │                  │
│  └────────┬────────┘  └─────────────────┘                  │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────────────────────────────────┐           │
│  │         Ray Object Store (Shared Memory)     │           │
│  │              ODB files, Checkpoints          │           │
│  └─────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  Worker Process  │ │  Worker Process  │ │  Worker Process  │
│  ┌────────────┐  │ │  ┌────────────┐  │ │  ┌────────────┐  │
│  │  OpenROAD  │  │ │  │  OpenROAD  │  │ │  │  OpenROAD  │  │
│  │  Trial N   │  │ │  │  Trial N+1 │  │ │  │  Trial N+2 │  │
│  └────────────┘  │ │  └────────────┘  │ │  └────────────┘  │
└──────────────────┘ └──────────────────┘ └──────────────────┘`;

export default function Slide06() {
  return (
    <Slide>
      <h1>Ray Architecture for Noodle2</h1>
      <pre><code>{diagram}</code></pre>
    </Slide>
  );
}
