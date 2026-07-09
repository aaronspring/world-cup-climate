import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { Pin } from "./types";
import { tempColor, tempRGB } from "./colors";

interface Grid { bounds: [number, number, number, number]; nx: number; ny: number; values: (number | null)[] }

// Web-Mercator northing for a latitude in degrees, and its inverse.
const mercY = (lat: number) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
const invMercY = (y: number) => (360 / Math.PI) * Math.atan(Math.exp(y)) - 90;

// Colorize a t2m grid (row-major from NW, equirectangular) into a data-URL +
// image coordinates. MapLibre's image source maps the texture *linearly in
// Web-Mercator* between the corner coords, but our rows are evenly spaced in
// *latitude* — so we resample rows into Mercator-even spacing here, else the
// field drifts north by several degrees at mid-latitudes. Longitude is already
// linear in Mercator, so columns pass through untouched (nearest-row sampling
// only; no values are averaged or invented).
async function loadOverlay(url: string) {
  const g: Grid = await (await fetch(url)).json();
  const [w, s, e, n] = g.bounds; // cell edges
  const cv = document.createElement("canvas");
  cv.width = g.nx;
  cv.height = g.ny;
  const ctx = cv.getContext("2d")!;
  const img = ctx.createImageData(g.nx, g.ny);
  const yN = mercY(n), yS = mercY(s);
  for (let row = 0; row < g.ny; row++) {
    // Latitude this output row must show so it lands correctly in Mercator.
    const lat = invMercY(yN + ((yS - yN) * (row + 0.5)) / g.ny);
    let src = Math.floor(((n - lat) / (n - s)) * g.ny); // nearest source row
    src = Math.min(g.ny - 1, Math.max(0, src));
    for (let col = 0; col < g.nx; col++) {
      const v = g.values[src * g.nx + col];
      const o = (row * g.nx + col) * 4;
      if (v == null) { img.data[o + 3] = 0; continue; } // masked/ocean -> transparent
      const [r, gg, b] = tempRGB(v);
      img.data[o] = r; img.data[o + 1] = gg; img.data[o + 2] = b; img.data[o + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  // image-source coordinates: TL, TR, BR, BL
  const coordinates: [[number, number], [number, number], [number, number], [number, number]] =
    [[w, n], [e, n], [e, s], [w, s]];
  return { url: cv.toDataURL(), coordinates };
}

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
        // Pending (beyond forecast horizon) → neutral gray pin with an em dash.
        color: p.t2m_at_kickoff == null ? "#64748b" : tempColor(p.t2m_at_kickoff),
        temp: p.t2m_at_kickoff == null ? "—" : `${Math.round(p.t2m_at_kickoff)}°`,
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

const DATA_BASE = `${import.meta.env.BASE_URL}data`;

export default function MapView({
  pins,
  selectedId,
  onSelect,
  overlayMap,
}: {
  pins: Pin[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  overlayMap: string | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const readyRef = useRef(false);
  const [ready, setReady] = useState(false); // re-trigger data-driven effects once `load` fires
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
      setReady(true);
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

  // t2m field overlay for the selected (or first) match's valid time.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    if (!overlayMap) {
      if (map.getLayer("t2m")) map.setLayoutProperty("t2m", "visibility", "none");
      return;
    }
    let alive = true;
    loadOverlay(`${DATA_BASE}/${overlayMap}`).then(({ url, coordinates }) => {
      if (!alive || !mapRef.current) return;
      const src = map.getSource("t2m") as maplibregl.ImageSource | undefined;
      if (src) {
        src.updateImage({ url, coordinates });
        map.setLayoutProperty("t2m", "visibility", "visible");
      } else {
        map.addSource("t2m", { type: "image", url, coordinates });
        map.addLayer(
          { id: "t2m", type: "raster", source: "t2m", paint: { "raster-opacity": 0.55 } },
          "pin-glow",
        );
      }
    });
    return () => {
      alive = false;
    };
  }, [overlayMap, ready]);

  // maplibre-gl.css forces `.maplibregl-map { position: relative }`, so size the
  // container explicitly with h/w-full rather than relying on `absolute inset-0`.
  return <div ref={containerRef} className="h-full w-full" />;
}
