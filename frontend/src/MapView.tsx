import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { Pin } from "./types";
import { tempColor } from "./colors";

// Inline style: a background layer makes `load` fire instantly (so pins always
// render), with CARTO dark raster tiles painted on top when the network is up.
const STYLE: maplibregl.StyleSpecification = {
  version: 8,
  glyphs: "https://fonts.openmaptiles.org/{fontstack}/{range}.pbf",
  sources: {
    basemap: {
      type: "raster",
      tiles: ["https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png"],
      tileSize: 256,
      attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a> © <a href="https://carto.com/attributions">CARTO</a>',
    },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#0a0e16" } },
    { id: "basemap", type: "raster", source: "basemap", paint: { "raster-opacity": 0.9 } },
  ],
};

function features(pins: Pin[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: pins.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.venue.lon, p.venue.lat] },
      properties: {
        id: p.id,
        color: tempColor(p.t2m_at_kickoff),
        temp: `${Math.round(p.t2m_at_kickoff)}°`,
      },
    })),
  };
}

const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

// Frame the day's venues, leaving room for the header and (on desktop) the list/card.
function fitToPins(map: maplibregl.Map, pins: Pin[]) {
  if (pins.length === 0) return;
  const wide = window.innerWidth >= 640;
  const pad = { top: 140, bottom: 70, left: wide ? 330 : 50, right: wide ? 60 : 50 };
  if (pins.length === 1) {
    map.easeTo({ center: [pins[0].venue.lon, pins[0].venue.lat], zoom: 5, padding: pad, duration: 600 });
    return;
  }
  const b = new maplibregl.LngLatBounds();
  for (const p of pins) b.extend([p.venue.lon, p.venue.lat]);
  map.fitBounds(b, { padding: pad, maxZoom: 6, duration: 600 });
}

export default function MapView({
  pins,
  selectedId,
  onSelect,
}: {
  pins: Pin[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const readyRef = useRef(false);
  const pinsRef = useRef(pins); // always-latest pins for the async `load` handler
  pinsRef.current = pins;

  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE,
      center: [-100, 37],
      zoom: 3.1,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    mapRef.current = map;

    map.on("load", () => {
      map.addSource("pins", { type: "geojson", data: EMPTY });
      map.addLayer({
        id: "pin-glow",
        type: "circle",
        source: "pins",
        paint: {
          "circle-radius": ["case", ["==", ["get", "id"], ""], 26, 22],
          "circle-color": ["get", "color"],
          "circle-blur": 1,
          "circle-opacity": 0.45,
        },
      });
      map.addLayer({
        id: "pin-dot",
        type: "circle",
        source: "pins",
        paint: {
          "circle-radius": 13,
          "circle-color": ["get", "color"],
          "circle-stroke-width": 2,
          "circle-stroke-color": "rgba(255,255,255,0.9)",
        },
      });
      map.addLayer({
        id: "pin-label",
        type: "symbol",
        source: "pins",
        layout: {
          "text-field": ["get", "temp"],
          "text-size": 11,
          "text-font": ["Open Sans Bold"],
          "text-allow-overlap": true,
        },
        paint: {
          "text-color": "#0a0e16",
          "text-halo-color": "rgba(255,255,255,0.6)",
          "text-halo-width": 0.6,
        },
      });

      readyRef.current = true;
      (map.getSource("pins") as maplibregl.GeoJSONSource)?.setData(features(pinsRef.current));
      fitToPins(map, pinsRef.current);

      const click = (e: maplibregl.MapLayerMouseEvent) => {
        const id = e.features?.[0]?.properties?.id;
        if (id) onSelect(id as string);
      };
      map.on("click", "pin-dot", click);
      map.on("click", "pin-label", click);
      for (const l of ["pin-dot", "pin-label"]) {
        map.on("mouseenter", l, () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", l, () => (map.getCanvas().style.cursor = ""));
      }
    });

    return () => map.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Push new pins whenever the day changes.
  useEffect(() => {
    if (!readyRef.current || !mapRef.current) return;
    (mapRef.current.getSource("pins") as maplibregl.GeoJSONSource)?.setData(features(pins));
    fitToPins(mapRef.current, pins);
  }, [pins]);

  // Emphasize the selected pin.
  useEffect(() => {
    const map = mapRef.current;
    if (!readyRef.current || !map) return;
    map.setPaintProperty("pin-dot", "circle-radius", [
      "case", ["==", ["get", "id"], selectedId ?? "__none__"], 17, 13,
    ]);
    map.setPaintProperty("pin-dot", "circle-stroke-width", [
      "case", ["==", ["get", "id"], selectedId ?? "__none__"], 3.5, 2,
    ]);
  }, [selectedId]);

  // maplibre-gl.css forces `.maplibregl-map { position: relative }`, so size the
  // container explicitly with h/w-full rather than relying on `absolute inset-0`.
  return <div ref={containerRef} className="h-full w-full" />;
}
