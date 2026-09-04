import { AnimatePresence, motion } from "framer-motion";
import L from "leaflet";
import { Crosshair, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { CircleMarker, MapContainer, Rectangle, TileLayer, useMap, useMapEvents } from "react-leaflet";
import { cn } from "../../lib/cn";
import Button from "../ui/Button";

const DEFAULT_CENTER = [22.35, 78.6];
const DEFAULT_ZOOM = 5;
const AOI_STEPS = ["AOI selected", "Calculating area…", "Ready for analysis"];

function CursorController({ active }) {
  const map = useMap();
  useEffect(() => {
    map.getContainer().style.cursor = active ? "crosshair" : "";
  }, [active, map]);
  return null;
}

function DrawHandler({ active, onChange, onComplete }) {
  const [start, setStart] = useState(null);

  useMapEvents({
    mousedown(e) {
      if (!active) return;
      e.target.dragging.disable();
      setStart(e.latlng);
      onChange(L.latLngBounds(e.latlng, e.latlng));
    },
    mousemove(e) {
      if (!active || !start) return;
      onChange(L.latLngBounds(start, e.latlng));
    },
    mouseup(e) {
      if (!active || !start) return;
      const finalBounds = L.latLngBounds(start, e.latlng);
      setStart(null);
      e.target.dragging.enable();
      const isDegenerate =
        finalBounds.getNorth() === finalBounds.getSouth() ||
        finalBounds.getEast() === finalBounds.getWest();
      onComplete(isDegenerate ? null : finalBounds);
    },
  });

  return null;
}

function computeAreaKm2(bounds) {
  const sw = bounds.getSouthWest();
  const widthM = sw.distanceTo(bounds.getSouthEast());
  const heightM = sw.distanceTo(bounds.getNorthWest());
  return (widthM * heightM) / 1e6;
}

/** Steps through "AOI selected" -> "Calculating area…" -> "Ready" once per new AOI. */
function useAoiStatusSequence(boundsKey) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (boundsKey === 0) return undefined;
    setStep(0);
    const t1 = setTimeout(() => setStep(1), 450);
    const t2 = setTimeout(() => setStep(2), 950);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [boundsKey]);

  return step;
}

export default function AOIMap({ onAoiChange, className }) {
  const [mapReady, setMapReady] = useState(false);
  const [drawing, setDrawing] = useState(false);
  const [bounds, setBounds] = useState(null);
  const boundsKeyRef = useRef(0);
  const [boundsKey, setBoundsKey] = useState(0);
  const statusStep = useAoiStatusSequence(boundsKey);

  function handleComplete(finalBounds) {
    setBounds(finalBounds);
    setDrawing(false);
    if (finalBounds) {
      boundsKeyRef.current += 1;
      setBoundsKey(boundsKeyRef.current);
    }
    onAoiChange?.(finalBounds ? boundsToAoi(finalBounds) : null);
  }

  function handleClear() {
    setBounds(null);
    onAoiChange?.(null);
  }

  const corners = bounds
    ? [bounds.getNorthWest(), bounds.getNorthEast(), bounds.getSouthEast(), bounds.getSouthWest()]
    : [];

  return (
    <div
      className={cn(
        "relative isolate overflow-hidden rounded-lg border border-border-strong",
        className,
      )}
    >
      <AnimatePresence>
        {!mapReady && (
          <motion.div
            initial={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="skeleton-shimmer absolute inset-0 z-[1100] flex items-center justify-center bg-bg-elevated text-xs text-text-muted"
          >
            Loading map tiles&hellip;
          </motion.div>
        )}
      </AnimatePresence>

      {/* subtle radar sweep across the map while actively drawing */}
      {drawing && (
        <motion.div
          className="pointer-events-none absolute inset-x-0 z-[900] h-px bg-gradient-to-r from-transparent via-accent/60 to-transparent"
          initial={{ top: "0%", opacity: 0 }}
          animate={{ top: ["0%", "100%"], opacity: [0, 1, 0] }}
          transition={{ repeat: Infinity, duration: 1.8, ease: "easeInOut" }}
        />
      )}

      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        scrollWheelZoom
        className="h-[420px] w-full"
        whenReady={() => setTimeout(() => setMapReady(true), 350)}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <CursorController active={drawing} />
        <DrawHandler active={drawing} onChange={setBounds} onComplete={handleComplete} />
        {bounds && (
          <Rectangle
            key={boundsKey}
            bounds={bounds}
            pathOptions={{
              color: "#22d3ee",
              weight: 2,
              fillOpacity: 0.12,
              className: "aoi-rectangle-active",
            }}
          />
        )}
        {bounds &&
          corners.map((corner, i) => (
            <CircleMarker
              key={`${boundsKey}-${i}`}
              center={corner}
              radius={4}
              pathOptions={{
                color: "#22d3ee",
                fillColor: "#22d3ee",
                fillOpacity: 1,
                weight: 1.5,
              }}
            />
          ))}
      </MapContainer>

      <div className="absolute left-3 top-3 z-[1000] flex gap-2">
        <Button
          type="button"
          size="sm"
          variant={drawing ? "primary" : "secondary"}
          icon={Crosshair}
          onClick={() => setDrawing((d) => !d)}
        >
          {drawing ? "Drawing…" : "Draw AOI"}
        </Button>
        {bounds && (
          <Button type="button" size="sm" variant="ghost" icon={Trash2} onClick={handleClear}>
            Clear
          </Button>
        )}
      </div>

      <AnimatePresence>
        {bounds && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            transition={{ duration: 0.2 }}
            className="absolute bottom-3 left-3 right-3 z-[1000] rounded-lg border border-border-strong bg-bg/90 p-3 backdrop-blur"
          >
            <div className="mb-2 flex items-center justify-between">
              <AnimatePresence mode="wait">
                <motion.span
                  key={statusStep}
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 4 }}
                  transition={{ duration: 0.15 }}
                  className={cn(
                    "text-xs font-medium",
                    statusStep === 2 ? "text-success" : "text-accent",
                  )}
                >
                  {AOI_STEPS[statusStep]}
                </motion.span>
              </AnimatePresence>
              <span className="text-xs text-text-secondary">
                &asymp; {computeAreaKm2(bounds).toLocaleString(undefined, { maximumFractionDigits: 0 })} km&sup2;
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-xs text-text-secondary sm:grid-cols-4">
              <span>N {bounds.getNorth().toFixed(4)}</span>
              <span>S {bounds.getSouth().toFixed(4)}</span>
              <span>E {bounds.getEast().toFixed(4)}</span>
              <span>W {bounds.getWest().toFixed(4)}</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function boundsToAoi(bounds) {
  return {
    north: bounds.getNorth(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    west: bounds.getWest(),
  };
}
