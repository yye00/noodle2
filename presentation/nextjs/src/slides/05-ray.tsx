import Slide from "@/components/Slide";

export default function Slide05() {
  return (
    <Slide>
      <h1>Ray - Distributed Parallel Execution</h1>
      <p><strong>Ray</strong> enables scalable parallel trial execution:</p>
      <p><strong>Single-Node Mode:</strong></p>
      <ul>
        <li>25 trials per stage execute in parallel</li>
        <li>Utilizes all CPU cores (32 cores in this demo)</li>
        <li>Shared memory for ODB file access</li>
      </ul>
      <p><strong>Multi-Node Mode (Cluster):</strong></p>
      <pre><code>{`# Head node
ray start --head --port=6379

# Worker nodes (join cluster)
ray start --address=<head-ip>:6379`}</code></pre>
      <p><strong>Benefits:</strong></p>
      <ul>
        <li>Linear scaling with additional nodes</li>
        <li>Fault tolerance (failed trials don&apos;t stop execution)</li>
        <li>Dashboard for monitoring (http://localhost:8265)</li>
      </ul>
    </Slide>
  );
}
