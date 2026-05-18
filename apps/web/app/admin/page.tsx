import { ApiError } from "../../components/common/ApiState";
import { KpiSection } from "../../components/dashboard/KpiSection";
import { getAdminKpis } from "../../lib/api";

export default async function AdminPage() {
  const result = await getAdminKpis();
  if (!result.ok) return <main><h1>Admin Dashboard</h1><ApiError title="Admin KPI API unavailable" error={result.error} /></main>;
  return (
    <main>
      <h1>Admin Dashboard</h1>
      <div className="grid">
        <KpiSection title="Collection KPI" data={result.data.collection} />
        <KpiSection title="XR / Isaac Runtime KPI" data={result.data.xr_runtime} />
        <KpiSection title="Evaluation KPI" data={result.data.evaluation} />
        <KpiSection title="Learning KPI" data={result.data.learning} />
      </div>
    </main>
  );
}
