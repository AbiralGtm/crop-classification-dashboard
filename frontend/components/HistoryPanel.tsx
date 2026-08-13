"use client";

import { useEffect, useState } from "react";
import { listAOIHistory, type AOIHistoryItem } from "@/lib/api";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-gray-200 text-gray-700",
  running: "bg-amber-100 text-amber-800",
  done: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

type Props = {
  onSelect: (item: AOIHistoryItem) => void;
  refreshKey: number; // bump this after a new classification completes to refetch
};

export default function HistoryPanel({ onSelect, refreshKey }: Props) {
  const [items, setItems] = useState<AOIHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listAOIHistory()
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  if (loading && items.length === 0) {
    return <div className="p-4 text-xs text-gray-400">Loading history…</div>;
  }

  if (items.length === 0) {
    return null;
  }

  return (
    <div className="border-b border-gray-200 p-4">
      <h3 className="mb-2 text-xs font-semibold text-gray-700">Past AOIs</h3>
      <ul className="max-h-40 space-y-1 overflow-y-auto">
        {items.map((item) => (
          <li key={item.aoi_id}>
            <button
              onClick={() => onSelect(item)}
              className="flex w-full items-center justify-between rounded px-1.5 py-1 text-left text-xs hover:bg-gray-50"
            >
              <span className="truncate text-gray-700">{item.name}</span>
              <span
                className={`ml-2 shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                  STATUS_STYLES[item.status] ?? "bg-gray-200 text-gray-700"
                }`}
              >
                {item.status}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
