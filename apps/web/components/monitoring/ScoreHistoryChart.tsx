import type { ScoreHistoryEntry } from "../../lib/types";

const WIDTH = 600;
const HEIGHT = 160;
const PADDING = 24;

function colorForScore(score: number): string {
  if (score >= 90) return "var(--color-pass)";
  if (score >= 70) return "var(--color-medium)";
  if (score >= 50) return "var(--color-high)";
  return "var(--color-critical)";
}

export function ScoreHistoryChart({ scores }: { scores: ScoreHistoryEntry[] }) {
  if (scores.length === 0) {
    return (
      <div className="rounded-lg border border-black/10 dark:border-white/10 p-4 text-sm text-black/50 dark:text-white/50">
        No score history yet — it fills in as scheduled scans complete.
      </div>
    );
  }

  // The API returns most-recent-first; chart reads chronologically left to right.
  const chronological = [...scores].reverse();
  const innerWidth = WIDTH - PADDING * 2;
  const innerHeight = HEIGHT - PADDING * 2;

  const points = chronological.map((entry, index) => {
    const x =
      chronological.length === 1
        ? PADDING + innerWidth / 2
        : PADDING + (index / (chronological.length - 1)) * innerWidth;
    const y = PADDING + innerHeight - (entry.score / 100) * innerHeight;
    return { x, y, entry };
  });

  const polyline = points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const first = chronological[0];
  const last = chronological[chronological.length - 1];

  return (
    <div className="rounded-lg border border-black/10 dark:border-white/10 p-4">
      <p className="text-sm font-semibold mb-2">Score history</p>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="Score over time"
        className="w-full h-auto"
      >
        <line
          x1={PADDING}
          y1={PADDING + innerHeight}
          x2={WIDTH - PADDING}
          y2={PADDING + innerHeight}
          stroke="currentColor"
          strokeOpacity={0.15}
        />
        <polyline
          points={polyline}
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth={2}
        />
        {points.map((p) => (
          <circle key={p.entry.scan_id} cx={p.x} cy={p.y} r={3.5} fill={colorForScore(p.entry.score)} />
        ))}
      </svg>
      <div className="flex justify-between text-xs text-black/50 dark:text-white/50 mt-1">
        <span>{new Date(first.created_at).toLocaleDateString()}</span>
        <span>{new Date(last.created_at).toLocaleDateString()}</span>
      </div>
    </div>
  );
}
