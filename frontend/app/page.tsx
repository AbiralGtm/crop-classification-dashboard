"use client";

import dynamic from "next/dynamic";
import { useCallback, useMemo, useState } from "react";
import Dashboard from "@/components/Dashboard";
import ExportPanel from "@/components/ExportPanel";
import HistoryPanel from "@/components/HistoryPanel";
import {
  getAOIStatus,
  pollAOI,
  submitAOI,
  type AOIHistoryItem,
  type ClassificationResult,
} from "@/lib/api";

const Map = dynamic(() => import("@/components/Map"), { ssr: false });

function geometryBounds(geometry: GeoJSON.Geometry): [[number, number], [number, number]] | null {
  if (geometry.type !== "Polygon") return null;
  const coords = geometry.coordinates[0] as [number, number][];
  const lats = coords.map((c) => c[1]);
  const lngs = coords.map((c) => c[0]);
  return [
    [Math.min(...lats), Math.min(...lngs)],
    [Math.max(...lats), Math.max(...lngs)],
  ];
}

// Default to a recent winter (rabi) crop season -- wheat/lentil/mustard --
// for the Rupandehi pilot; swap for the monsoon window (roughly Jun-Nov) to
// see rice instead.
const DEFAULT_START = "2025-11-01";
const DEFAULT_END = "2026-03-01";

export default function Home() {
  const [aoiName, setAoiName] = useState("Rupandehi pilot AOI");
  const [geometry, setGeometry] = useState<GeoJSON.Geometry | null>(null);
  const [startDate, setStartDate] = useState(DEFAULT_START);
  const [endDate, setEndDate] = useState(DEFAULT_END);
  const [result, setResult] = useState<ClassificationResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  const overlayBounds = useMemo(() => (geometry ? geometryBounds(geometry) : null), [geometry]);

  const handleClassify = useCallback(async () => {
    if (!geometry) {
      setErrorMsg("Draw an area of interest on the map first.");
      return;
    }
    setErrorMsg(null);
    setSubmitting(true);
    setResult(null);
    try {
      const { aoi_id } = await submitAOI({
        name: aoiName,
        geometry,
        start_date: startDate,
        end_date: endDate,
      });
      await pollAOI(aoi_id, setResult);
      setHistoryRefreshKey((k) => k + 1); // refresh the history list now that this AOI exists
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Classification failed");
    } finally {
      setSubmitting(false);
    }
  }, [geometry, aoiName, startDate, endDate]);

  const handleSelectHistoryItem = useCallback(async (item: AOIHistoryItem) => {
    setErrorMsg(null);
    setAoiName(item.name);
    setGeometry(item.geometry);
    setStartDate(item.start_date);
    setEndDate(item.end_date);
    setResult(null);
    try {
      const full = await getAOIStatus(item.aoi_id);
      setResult(full);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load that AOI's result.");
    }
  }, []);

  return (
    <main className="flex h-full w-full">
      <div className="relative flex-1">
        <Map
          onAOIChange={setGeometry}
          classifiedOverlayUrl={result?.thumbnail_url}
          overlayBounds={overlayBounds}
        />
      </div>

      <aside className="flex w-96 flex-col overflow-y-auto border-l border-gray-200 bg-white">
        <div className="space-y-3 border-b border-gray-200 p-4">
          <h1 className="text-lg font-semibold">Crop Classification</h1>
          <p className="text-xs text-gray-500">
            Draw a polygon/rectangle on the map to select an area of interest, then classify.
          </p>

          <label className="block text-xs font-medium text-gray-600">
            AOI name
            <input
              className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
              value={aoiName}
              onChange={(e) => setAoiName(e.target.value)}
            />
          </label>

          <div className="flex gap-2">
            <label className="block flex-1 text-xs font-medium text-gray-600">
              Start date
              <input
                type="date"
                className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </label>
            <label className="block flex-1 text-xs font-medium text-gray-600">
              End date
              <input
                type="date"
                className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </label>
          </div>

          <button
            onClick={handleClassify}
            disabled={submitting || !geometry}
            className="w-full rounded bg-green-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            {submitting ? "Classifying…" : "Classify AOI"}
          </button>

          {errorMsg && <p className="text-xs text-red-600">{errorMsg}</p>}
        </div>

        <HistoryPanel onSelect={handleSelectHistoryItem} refreshKey={historyRefreshKey} />

        <Dashboard result={result} />
        <ExportPanel aoiId={result?.aoi_id ?? null} disabled={result?.status !== "done"} />
      </aside>
    </main>
  );
}
