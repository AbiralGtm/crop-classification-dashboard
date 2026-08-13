"use client";

import { exportUrl } from "@/lib/api";

export default function ExportPanel({ aoiId, disabled }: { aoiId: string | null; disabled: boolean }) {
  return (
    <div className="flex gap-2 p-4 pt-0">
      <a
        className={`flex-1 rounded border px-3 py-2 text-center text-xs font-medium ${
          disabled ? "pointer-events-none border-gray-200 text-gray-300" : "border-gray-300 hover:bg-gray-50"
        }`}
        href={aoiId ? exportUrl(aoiId, "pdf") : "#"}
      >
        Download PDF report
      </a>
      <a
        className={`flex-1 rounded border px-3 py-2 text-center text-xs font-medium ${
          disabled ? "pointer-events-none border-gray-200 text-gray-300" : "border-gray-300 hover:bg-gray-50"
        }`}
        href={aoiId ? exportUrl(aoiId, "csv") : "#"}
      >
        Download CSV
      </a>
      <a
        className={`flex-1 rounded border px-3 py-2 text-center text-xs font-medium ${
          disabled ? "pointer-events-none border-gray-200 text-gray-300" : "border-gray-300 hover:bg-gray-50"
        }`}
        href={aoiId ? exportUrl(aoiId, "geotiff") : "#"}
      >
        Download GeoTIFF
      </a>
    </div>
  );
}
