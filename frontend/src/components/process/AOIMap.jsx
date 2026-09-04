import { AnimatePresence, motion } from "framer-motion";
import L from "leaflet";
import { Crosshair, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { MapContainer, Rectangle, TileLayer, useMap, useMapEvents } from "react-leaflet";
import { cn } from "../../lib/cn";
import Button from "../ui/Button";

const DEFAULT_CENTER = [22.35, 78.6];
const DEFAULT_ZOOM = 5;

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

export default function AOIMap({ onAoiChange, className }) {
  const [mapReady, setMapReady] = useState(false);
  const [drawing, setDrawing] = useState(false);
  const [bounds, setBounds] = useState(null);

  function handleComplete(finalBounds) {
    setBounds(finalBounds);
    setDrawing(false);
    onAoiChange?.(finalBounds ? boundsToAoi(finalBounds) : null);
  }

  function handleClear() {
    setBounds(null);
    onAoiChange?.(null);
  }

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
            bounds={bounds}
            pathOptions={{ color: "#22d3ee", weight: 2, fillOpacity: 0.12 }}
          />
        )}
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
