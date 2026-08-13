"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { AccuracyStats, ClassStat, ClassificationResult, DistrictComparison } from "@/lib/api";
import { CROP_PALETTE as PALETTE } from "@/lib/palette";

function StatusBadge({ status }: { status: ClassificationResult["status"] }) {
  const styles: Record<string, string> = {
    pending: "bg-gray-200 text-gray-700",
    running: "bg-amber-100 text-amber-800",
    done: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${styles[status]}`}>
      {status}
    </span>
  );
}

function AccuracySection({ accuracy }: { accuracy: AccuracyStats | null }) {
  if (!accuracy) return null;

  if (!accuracy.available) {
    return (
      <div className="rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
        <p className="font-medium">Accuracy not available yet</p>
        <p className="mt-1">{accuracy.reason ?? "Not enough labeled data for a held-out test split."}</p>
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded border border-gray-200 p-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-gray-700">Held-out accuracy</h3>
        <span className="text-[11px] text-gray-400">
          {accuracy.train_count} train / {accuracy.test_count} test pts
        </span>
      </div>

      <div className="flex gap-4 text-xs">
        <div>
          <span className="text-gray-500">Overall accuracy: </span>
          <span className="font-medium text-gray-800">
            {accuracy.overall_accuracy !== null ? `${(accuracy.overall_accuracy * 100).toFixed(1)}%` : "—"}
          </span>
        </div>
        <div>
          <span className="text-gray-500">Kappa: </span>
          <span className="font-medium text-gray-800">{accuracy.kappa?.toFixed(3) ?? "—"}</span>
        </div>
      </div>

      {accuracy.per_class.length > 0 && (
        <table className="w-full text-[11px]">
          <thead>
            <tr className="text-left text-gray-400">
              <th className="font-normal">Class</th>
              <th className="font-normal">Recall</th>
              <th className="font-normal">Precision</th>
            </tr>
          </thead>
          <tbody>
            {accuracy.per_class.map((c) => (
              <tr key={c.class_name}>
                <td className="py-0.5">{c.class_name}</td>
                <td>{c.recall !== null ? c.recall.toFixed(2) : "—"}</td>
                <td>{c.precision !== null ? c.precision.toFixed(2) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {accuracy.note && <p className="text-[11px] italic text-gray-400">{accuracy.note}</p>}
    </div>
  );
}

function DistrictComparisonSection({ comparison }: { comparison: DistrictComparison | null }) {
  if (!comparison || comparison.aoi_pct_of_district_cereal_area === null) return null;

  const pct = comparison.aoi_pct_of_district_cereal_area ?? 0;
  const looksImplausible = pct > 100;

  return (
    <div
      className={`space-y-1 rounded border p-2 text-[11px] ${
        looksImplausible ? "border-red-200 bg-red-50 text-red-800" : "border-gray-200 text-gray-600"
      }`}
    >
      <p className="text-xs font-semibold text-gray-700">District scale check</p>
      <p>
        AOI cropped area: <span className="font-medium">{comparison.aoi_cropped_area_ha?.toFixed(2)} ha</span>{" "}
        (~{pct.toFixed(3)}% of {comparison.district_name}&apos;s {comparison.district_major_cereal_area_ha?.toLocaleString()} ha
        major-cereal area, {comparison.fiscal_year})
      </p>
      {looksImplausible && (
        <p className="font-medium">
          This AOI predicts more cropped area than plausible for its size -- likely a classification issue.
        </p>
      )}
      {comparison.note && <p className="italic text-gray-400">{comparison.note}</p>}
      {comparison.source && <p className="text-gray-400">Source: {comparison.source}</p>}
    </div>
  );
}

export default function Dashboard({ result }: { result: ClassificationResult | null }) {
  if (!result) {
    return (
      <div className="p-4 text-sm text-gray-500">
        Draw an area of interest on the map, pick a date range, and classify to see results here.
      </div>
    );
  }

  const totalHa = result.class_stats.reduce((sum, c) => sum + c.area_hectares, 0);

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700">Classification results</h2>
        <StatusBadge status={result.status} />
      </div>

      {result.error && (
        <p className="rounded bg-red-50 p-2 text-xs text-red-700">{result.error}</p>
      )}

      {result.status === "done" && result.class_stats.length > 0 && (
        <>
          <div className="text-xs text-gray-500">
            Total classified area: <span className="font-medium text-gray-800">{totalHa.toFixed(2)} ha</span>
          </div>

          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={result.class_stats} layout="vertical" margin={{ left: 24 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis dataKey="class_name" type="category" tick={{ fontSize: 11 }} width={80} />
                <Tooltip formatter={(v: number) => `${v.toFixed(2)} ha`} />
                <Bar dataKey="area_hectares">
                  {result.class_stats.map((entry: ClassStat) => (
                    <Cell key={entry.class_id} fill={PALETTE[entry.class_name] ?? "#8884d8"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <ul className="space-y-1 text-xs">
            {result.class_stats.map((c) => (
              <li key={c.class_id} className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-sm"
                    style={{ backgroundColor: PALETTE[c.class_name] ?? "#8884d8" }}
                  />
                  {c.class_name}
                </span>
                <span className="text-gray-500">{c.area_hectares.toFixed(2)} ha</span>
              </li>
            ))}
          </ul>

          <AccuracySection accuracy={result.accuracy} />
          <DistrictComparisonSection comparison={result.district_comparison} />
        </>
      )}
    </div>
  );
}
