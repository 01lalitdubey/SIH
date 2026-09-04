import { AnimatePresence, motion } from "framer-motion";
import { Image as ImageIcon, Info, MapPinned, UploadCloud } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import Button from "../components/ui/Button";
import Card, { CardHeader } from "../components/ui/Card";
import ImageContainer from "../components/ui/ImageContainer";
import { cn } from "../lib/cn";

const SOURCE_TABS = [
  { id: "upload", label: "Upload Image", icon: ImageIcon },
  { id: "aoi", label: "Select AOI", icon: MapPinned },
];

const SCALE_OPTIONS = [2, 4];

export default function Process() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [sourceTab, setSourceTab] = useState("upload");
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [aoiSelected, setAoiSelected] = useState(false);
  const [jobName, setJobName] = useState("");
  const [scaleFactor, setScaleFactor] = useState(4);
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = useMemo(() => {
    const hasSource = sourceTab === "upload" ? Boolean(file) : aoiSelected;
    return hasSource && jobName.trim().length > 0 && !submitting;
  }, [sourceTab, file, aoiSelected, jobName, submitting]);

  function handleFileChange(e) {
    const selected = e.target.files?.[0];
    if (!selected) return;
    setFile(selected);
    setPreviewUrl(URL.createObjectURL(selected));
  }

  function handleDrop(e) {
    e.preventDefault();
    const dropped = e.dataTransfer.files?.[0];
    if (!dropped) return;
    setFile(dropped);
    setPreviewUrl(URL.createObjectURL(dropped));
  }

  function handleSubmit() {
    if (!canSubmit) return;
    setSubmitting(true);
    // MOCK/TEMPORARY — no backend yet (Phase 4). Simulate submission latency,
    // then route to an existing mock job so the Results page can be demoed.
    setTimeout(() => {
      navigate("/results/job-1041");
    }, 600);
  }

  return (
    <div>
      <PageHeader
        title="New Analysis"
        description="Upload imagery or select an area of interest to begin."
      />

      <div className="rounded-lg border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-warning">
        <Info className="mr-2 inline size-4" aria-hidden="true" />
        Processing is mocked in this phase — no image is actually sent anywhere yet.
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader title="Imagery Source" subtitle="Choose how to provide input imagery" />

            <div className="mb-5 inline-flex rounded-lg border border-border bg-bg-elevated p-1">
              {SOURCE_TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setSourceTab(tab.id)}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    sourceTab === tab.id
                      ? "bg-accent-soft text-accent"
                      : "text-text-secondary hover:text-text-primary",
                  )}
                >
                  <tab.icon className="size-4" aria-hidden="true" />
                  {tab.label}
                </button>
              ))}
            </div>

            <AnimatePresence mode="wait">
              {sourceTab === "upload" ? (
                <motion.div
                  key="upload"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15 }}
                >
                  {previewUrl ? (
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <ImageContainer src={previewUrl} alt="Selected upload preview" />
                      <div className="flex flex-col justify-center gap-2">
                        <p className="text-sm font-medium text-text-primary">{file?.name}</p>
                        <p className="text-xs text-text-muted">
                          {(file?.size / 1024).toFixed(0)} KB
                        </p>
                        <Button
                          size="sm"
                          variant="secondary"
                          className="mt-2 w-fit"
                          onClick={() => fileInputRef.current?.click()}
                        >
                          Replace image
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={handleDrop}
                      onClick={() => fileInputRef.current?.click()}
                      className="flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border-strong bg-bg-elevated px-6 py-14 text-center transition-colors hover:border-accent/50"
                    >
                      <div className="flex size-12 items-center justify-center rounded-full border border-accent/30 bg-accent-soft">
                        <UploadCloud className="size-5 text-accent" aria-hidden="true" />
                      </div>
                      <p className="text-sm font-medium text-text-primary">
                        Drag & drop imagery, or click to browse
                      </p>
                      <p className="text-xs text-text-muted">GeoTIFF, JPEG, PNG supported</p>
                    </div>
                  )}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*,.tif,.tiff"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                </motion.div>
              ) : (
                <motion.div
                  key="aoi"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  className="scan-grid-bg flex flex-col items-center justify-center gap-3 rounded-lg border border-border-strong bg-bg-elevated px-6 py-14 text-center"
                >
                  <div className="flex size-12 items-center justify-center rounded-full border border-accent/30 bg-accent-soft">
                    <MapPinned className="size-5 text-accent" aria-hidden="true" />
                  </div>
                  <p className="text-sm font-medium text-text-primary">
                    Interactive AOI map arrives in Phase 5
                  </p>
                  <p className="max-w-sm text-xs text-text-muted">
                    Satellite search &amp; AOI drawing will connect to Copernicus Data
                    Space. For now, use the mock selection below.
                  </p>
                  <Button
                    size="sm"
                    variant={aoiSelected ? "primary" : "secondary"}
                    onClick={() => setAoiSelected(true)}
                  >
                    {aoiSelected ? "Mock AOI selected" : "Select Mock AOI"}
                  </Button>
                </motion.div>
              )}
            </AnimatePresence>
          </Card>
        </div>

        <div>
          <Card>
            <CardHeader title="Configuration" />
            <div className="flex flex-col gap-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-text-secondary">
                  Analysis name
                </label>
                <input
                  type="text"
                  value={jobName}
                  onChange={(e) => setJobName(e.target.value)}
                  placeholder="e.g. Coastal Delta — Sundarbans"
                  className="w-full rounded-lg border border-border-strong bg-bg-elevated px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-medium text-text-secondary">
                  Scale factor
                </label>
                <div className="flex gap-2">
                  {SCALE_OPTIONS.map((factor) => (
                    <button
                      key={factor}
                      onClick={() => setScaleFactor(factor)}
                      className={cn(
                        "flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors",
                        scaleFactor === factor
                          ? "border-accent/50 bg-accent-soft text-accent"
                          : "border-border-strong text-text-secondary hover:text-text-primary",
                      )}
                    >
                      {factor}x
                    </button>
                  ))}
                </div>
              </div>

              <Button
                onClick={handleSubmit}
                disabled={!canSubmit}
                loading={submitting}
                className="mt-2 w-full"
              >
                {submitting ? "Submitting" : "Run Analysis"}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
