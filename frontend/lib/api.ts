const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type ClassStat = {
  class_id: number;
  class_name: string;
  area_hectares: number;
};

export type AccuracyPerClass = {
  class_name: string;
  recall: number | null;
  precision: number | null;
};

// Held-out validation accuracy from a random train/test split of the labeled
// training points. `available: false` means the split was too small to mean
// anything -- expected while the label set is still placeholder data.
export type AccuracyStats = {
  available: boolean;
  train_count: number | null;
  test_count: number | null;
  overall_accuracy: number | null;
  kappa: number | null;
  per_class: AccuracyPerClass[];
  note: string | null;
  reason: string | null;
};

// Rough sanity check of the AOI's total predicted cropped area against
// Rupandehi district's published major-cereal area. Not a per-crop
// validation, just an order-of-magnitude scale check.
export type DistrictComparison = {
  district_name: string;
  district_major_cereal_area_ha: number | null;
  fiscal_year: string | null;
  source: string | null;
  aoi_cropped_area_ha: number | null;
  aoi_pct_of_district_cereal_area: number | null;
  note: string | null;
};

export type ClassificationResult = {
  aoi_id: string;
  status: "pending" | "running" | "done" | "failed";
  thumbnail_url: string | null;
  geotiff_url: string | null;
  class_stats: ClassStat[];
  accuracy: AccuracyStats | null;
  district_comparison: DistrictComparison | null;
  error: string | null;
};

export type AOIHistoryItem = {
  aoi_id: string;
  name: string;
  status: "pending" | "running" | "done" | "failed";
  start_date: string;
  end_date: string;
  geometry: GeoJSON.Geometry;
  created_at: string;
};

export type AOIRequest = {
  name: string;
  geometry: GeoJSON.Geometry;
  start_date: string; // YYYY-MM-DD
  end_date: string;
  labels_source?: string;
};

export async function submitAOI(req: AOIRequest): Promise<{ aoi_id: string; status: string }> {
  const res = await fetch(`${API_BASE_URL}/aoi`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Failed to submit AOI: ${res.status} ${await res.text()}`);
  return res.json();
}

export async function getAOIStatus(aoiId: string): Promise<ClassificationResult> {
  const res = await fetch(`${API_BASE_URL}/aoi/${aoiId}/status`);
  if (!res.ok) throw new Error(`Failed to fetch AOI status: ${res.status}`);
  return res.json();
}

export async function listCrops(): Promise<string[]> {
  const res = await fetch(`${API_BASE_URL}/crops`);
  if (!res.ok) throw new Error("Failed to fetch crop classes");
  return res.json();
}

export function exportUrl(aoiId: string, format: "pdf" | "csv" | "geotiff"): string {
  return `${API_BASE_URL}/export/${aoiId}/${format}`;
}

/** Past AOI requests, most recent first. Includes each item's geometry so it
 * can be redrawn on the map; fetch the full result separately via
 * getAOIStatus(aoi_id) when the user selects one. */
export async function listAOIHistory(limit = 50): Promise<AOIHistoryItem[]> {
  const res = await fetch(`${API_BASE_URL}/aoi?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch AOI history");
  return res.json();
}

/** The labeled training polygons used to train the classifier (currently
 * placeholder data for the Rupandehi pilot -- see backend/training/labels). */
export async function getTrainingLabels(): Promise<GeoJSON.FeatureCollection> {
  const res = await fetch(`${API_BASE_URL}/labels`);
  if (!res.ok) throw new Error("Failed to fetch training labels");
  return res.json();
}

/** Poll AOI status until done/failed, calling onUpdate after each check. */
export async function pollAOI(
  aoiId: string,
  onUpdate: (result: ClassificationResult) => void,
  intervalMs = 3000,
  timeoutMs = 5 * 60 * 1000
): Promise<ClassificationResult> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const result = await getAOIStatus(aoiId);
    onUpdate(result);
    if (result.status === "done" || result.status === "failed") return result;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("Timed out waiting for classification result");
}
