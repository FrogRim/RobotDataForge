import { KeyValueTable } from "../common/KeyValueTable";

export function KpiSection({ title, data }: { title: string; data: Record<string, unknown> }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      <KeyValueTable data={data} />
    </section>
  );
}
