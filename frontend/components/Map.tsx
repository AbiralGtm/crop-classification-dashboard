"use client";

import { useEffect, useRef, useState } from "react";
import {
  MapContainer,
  TileLayer,
  LayersControl,
  // Aliased: importing this as `GeoJSON` would shadow the global `GeoJSON`
  // namespace (from @types/geojson, pulled in transitively via
  // @types/leaflet) that the `GeoJSON.Geometry` / `GeoJSON.FeatureCollection`
  // types below rely on.
  GeoJSON as GeoJSONLayer,
  useMap,
} from "react-leaflet";
import L from "leaflet";

import { getTrainingLabels } from "@/lib/api";
import { CROP_PALETTE } from "@/lib/palette";

// leaflet-draw expects `window.L` to already exist when it loads (it patches
// the global L object rather than the ES module reference). A plain
// `import "leaflet-draw"` doesn't guarantee that ordering under
// webpack/Next.js, which silently leaves L.Control.Draw undefined and the
// draw toolbar never appears -- so require() it after setting window.L.
if (typeof window !== "undefined") {
  (window as any).L = L;
  require("leaflet-draw");
}

// Rupandehi District, Lumbini Province -- Terai farmland near
// Siddharthanagar/Bhairahawa.
const RUPANDEHI_CENTER: [number, number] = [27.4833, 83.45];

type Props = {
  onAOIChange: (geometry: GeoJSON.Geometry | null) => void;
  classifiedOverlayUrl?: string | null;
  overlayBounds?: [[number, number], [number, number]] | null;
};

function DrawControl({ onAOIChange }: Pick<Props, "onAOIChange">) {
  const map = useMap();
  const drawnItemsRef = useRef<L.FeatureGroup | null>(null);

  useEffect(() => {
    const drawnItems = new L.FeatureGroup();
    drawnItemsRef.current = drawnItems;
    map.addLayer(drawnItems);

    const drawControl = new (L.Control as any).Draw({
      draw: {
        polygon: true,
        rectangle: true,
        circle: false,
        circlemarker: false,
        marker: false,
        polyline: false,
      },
      edit: { featureGroup: drawnItems, remove: true },
    });
    map.addControl(drawControl);

    const handleCreated = (e: any) => {
      drawnItems.clearLayers(); // single AOI at a time for the MVP
      drawnItems.addLayer(e.layer);
      onAOIChange(e.layer.toGeoJSON().geometry);
    };
    const handleDeleted = () => onAOIChange(null);

    map.on((L as any).Draw.Event.CREATED, handleCreated);
    map.on((L as any).Draw.Event.DELETED, handleDeleted);

    return () => {
      map.off((L as any).Draw.Event.CREATED, handleCreated);
      map.off((L as any).Draw.Event.DELETED, handleDeleted);
      map.removeControl(drawControl);
      map.removeLayer(drawnItems);
    };
  }, [map, onAOIChange]);

  return null;
}

function TrainingLabelsLayer() {
  const [labels, setLabels] = useState<GeoJSON.FeatureCollection | null>(null);

  useEffect(() => {
    let cancelled = false;
    getTrainingLabels()
      .then((data) => {
        if (!cancelled) setLabels(data);
      })
      .catch(() => {
        if (!cancelled) setLabels(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!labels) return null;

  return (
    <GeoJSONLayer
      data={labels}
      style={(feature) => {
        const cropName = feature?.properties?.crop_name ?? "non_crop";
        return {
          color: CROP_PALETTE[cropName] ?? "#8884d8",
          weight: 2,
          fillOpacity: 0.45,
        };
      }}
      onEachFeature={(feature, layer) => {
        const { crop_name, note } = feature.properties ?? {};
        layer.bindPopup(`<strong>${crop_name ?? "unknown"}</strong><br/>${note ?? ""}`);
      }}
    />
  );
}

function ClassifiedOverlay({ url, bounds }: { url?: string | null; bounds?: Props["overlayBounds"] }) {
  const map = useMap();
  const overlayRef = useRef<L.ImageOverlay | null>(null);

  useEffect(() => {
    if (overlayRef.current) {
      map.removeLayer(overlayRef.current);
      overlayRef.current = null;
    }
    if (url && bounds) {
      const overlay = L.imageOverlay(url, bounds, { opacity: 0.75 });
      overlay.addTo(map);
      overlayRef.current = overlay;
    }
  }, [map, url, bounds]);

  return null;
}

export default function Map({ onAOIChange, classifiedOverlayUrl, overlayBounds }: Props) {
  return (
    <MapContainer center={RUPANDEHI_CENTER} zoom={13} className="h-full w-full">
      <LayersControl position="topright">
        <LayersControl.BaseLayer checked name="Satellite">
          <TileLayer
            attribution="Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS user community"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            maxZoom={19}
          />
        </LayersControl.BaseLayer>
        <LayersControl.BaseLayer name="Street">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
        </LayersControl.BaseLayer>
        <LayersControl.Overlay checked name="Training labels (placeholder)">
          <TrainingLabelsLayer />
        </LayersControl.Overlay>
      </LayersControl>
      <DrawControl onAOIChange={onAOIChange} />
      <ClassifiedOverlay url={classifiedOverlayUrl} bounds={overlayBounds} />
    </MapContainer>
  );
}
