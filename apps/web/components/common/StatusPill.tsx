export function StatusPill({ value }: { value: string }) {
  const tone = value === "completed" || value === "active" || value === "exported" ? "good" : value === "invalid" ? "bad" : "neutral";
  return <span className={`status ${tone}`}>{value}</span>;
}
