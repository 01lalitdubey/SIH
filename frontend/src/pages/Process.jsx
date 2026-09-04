import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  Image as ImageIcon,
  Info,
  Loader2,
  MapPinned,
  UploadCloud,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createProcessingJob, uploadImage } from "../api/client";
import IndeterminateBar from "../components/common/IndeterminateBar";
import PageHeader from "../components/layout/PageHeader";
import AOIMap from "../components/process/AOIMap";
import ProcessingStages, { STAGE_LABELS } from "../components/process/ProcessingStages";
import Button from "../components/ui/Button";
import Card, { CardHeader } from "../components/ui/Card";
import ImageContainer from "../components/ui/ImageContainer";
import Modal from "../components/ui/Modal";
import { useProcessingPoll } from "../hooks/useProcessingPoll";
import { cn } from "../lib/cn";
import { stageKeyToIndex, toProcessingUiStatus } from "../lib/jobStatus";

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
  const [imageId, setImageId] = useState(null);
  // "empty" | "uploading" | "loaded" | "error"
  const [uploadStage, setUploadStage] = useState("empty");
  const [uploadError, setUploadError] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [aoi, setAoi] = useState(null);
  const [jobName, setJobName] = useState("");
  const [scaleFactor, setScaleFactor] = useState(4);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // "form" | "processing"
  const [view, setView] = useState("form");
  const [jobId, setJobId] = useState(null);
  const shouldFailRef = useRef(false);

  const { job, error: pollError } = useProcessingPoll(view === "processing" ? jobId : null);

  const canSubmit = useMemo(() => {
    const hasSource =
      sourceTab === "upload" ? uploadStage === "loaded" && Boolean(imageId) : Boolean(aoi);
    return hasSource && jobName.trim().length > 0;
  }, [sourceTab, uploadStage, imageId, aoi, jobName]);

  async function ingestFile(selected) {
    setFile(selected);
    setImageId(null);
    setUploadStage("uploading");
    setUploadError(null);

    try {
      const image = await uploadImage(selected);
      setPreviewUrl(URL.createObjectURL(selected));
      setImageId(image.id);
      setUploadStage("loaded");
    } catch (err) {
      setUploadStage("error");
      setUploadError(err.message);
    }
  }

  function handleFileChange(e) {
    const selected = e.target.files?.[0];
    if (!selected) return;
    ingestFile(selected);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragActive(false);
    const dropped = e.dataTransfer.files?.[0];
    if (!dropped) return;
    ingestFile(dropped);
  }

  function resetUpload() {
    setFile(null);
    setPreviewUrl(null);
    setImageId(null);
    setUploadError(null);
    setUploadStage("empty");
  }

  async function runAnalysis(simulateFailure) {
    shouldFailRef.current = simulateFailure;
    setSubmitError(null);
    setSubmitting(true);
    try {
      const payload = {
        analysis_name: jobName,
        scale_factor: scaleFactor,
        simulate_failure: simulateFailure,
      };
      if (sourceTab === "upload") {
        payload.image_id = imageId;
      } else {
        payload.aoi = aoi;
      }

      const created = await createProcessingJob(payload);
      setJobId(created.job_id);
      setView("processing");
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  function handleConfirmRun() {
    setConfirmOpen(false);
    runAnalysis(false);
  }

  function handleRetry() {
    runAnalysis(shouldFailRef.current);
  }

  useEffect(() => {
    if (job?.status !== "completed") return undefined;
    const timer = setTimeout(() => navigate(`/results/${job.job_id}`), 1000);
    return () => clearTimeout(timer);
  }, [job, navigate]);

  const uiStatus = pollError ? "error" : job ? toProcessingUiStatus(job.status) : "processing";
  const uiStageIndex = job ? stageKeyToIndex(job.current_stage) : -1;

  return (
    <AnimatePresence mode="wait">
      {view === "processing" ? (
        <motion.div
          key="processing"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="mx-auto max-w-xl"
        >
        <PageHeader
          title={jobName || "New Analysis"}
          description={
            pollError
              ? "Lost contact with the backend."
              : job?.status === "failed"
                ? "Processing failed."
                : job?.status === "completed"
                  ? "Processing complete — redirecting to results…"
                  : "Running the super-resolution pipeline."
          }
        />

        <Card>
          <ProcessingStages stageIndex={uiStageIndex} status={uiStatus} />

          <AnimatePresence mode="wait">
            {job?.status === "completed" && (
              <motion.div
                key="completed"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-6 flex items-center gap-2 rounded-lg border border-success/30 bg-success-soft px-4 py-3 text-sm text-success"
              >
                <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
                All stages complete.
              </motion.div>
            )}

            {job?.status === "failed" && (
              <motion.div
                key="failed"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-6 space-y-3"
              >
                <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
                  <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
                  {job.error_message ||
                    `Stage "${STAGE_LABELS[uiStageIndex] ?? "unknown"}" failed.`}
                </div>
                <div className="flex gap-3">
                  <Button size="sm" onClick={handleRetry}>
                    Retry
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => setView("form")}>
                    Back to Form
                  </Button>
                </div>
              </motion.div>
            )}

            {pollError && (
              <motion.div
                key="poll-error"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-6 space-y-3"
              >
                <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
                  <XCircle className="size-4 shrink-0" aria-hidden="true" />
                  {pollError.isNetworkError
                    ? "Couldn't reach the backend to check status. It may be offline."
                    : pollError.message}
                </div>
                <Button size="sm" variant="secondary" onClick={() => setView("form")}>
                  Back to Form
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </Card>
        </motion.div>
      ) : (
        <motion.div
          key="form"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
        >
      <PageHeader
        title="New Analysis"
        description="Upload imagery or select an area of interest to begin."
      />

      <div className="rounded-lg border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-warning">
        <Info className="mr-2 inline size-4" aria-hidden="true" />
        Processing runs on the backend's mock pipeline — no real AI model yet.
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
                    "relative flex items-center gap-2 overflow-hidden rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    sourceTab === tab.id
                      ? "text-accent"
                      : "text-text-secondary hover:text-text-primary",
                  )}
                >
                  {sourceTab === tab.id && (
                    <motion.span
                      layoutId="source-tab-indicator"
                      transition={{ type: "spring", stiffness: 500, damping: 34 }}
                      className="absolute inset-0 bg-accent-soft"
                    />
                  )}
                  <tab.icon className="relative size-4" aria-hidden="true" />
                  <span className="relative">{tab.label}</span>
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
                  <AnimatePresence mode="wait">
                    {uploadStage === "loaded" ? (
                      <motion.div
                        key="loaded"
                        initial={{ opacity: 0, scale: 0.98 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.3, ease: "easeOut" }}
                        className="grid grid-cols-1 gap-4 sm:grid-cols-2"
                      >
                        <ImageContainer src={previewUrl} alt="Selected upload preview" />
                        <div className="flex flex-col justify-center gap-2">
                          <motion.p
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.1 }}
                            className="flex items-center gap-1.5 text-xs font-medium text-success"
                          >
                            <CheckCircle2 className="size-3.5" aria-hidden="true" />
                            Ready for analysis
                          </motion.p>
                          <p className="text-sm font-medium text-text-primary">{file?.name}</p>
                          <p className="text-xs text-text-muted">
                            {(file?.size / 1024).toFixed(0)} KB
                          </p>
                          <Button
                            size="sm"
                            variant="secondary"
                            className="mt-2 w-fit"
                            onClick={resetUpload}
                          >
                            Replace image
                          </Button>
                        </div>
                      </motion.div>
                    ) : uploadStage === "uploading" ? (
                      <motion.div
                        key="uploading"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="flex flex-col items-center justify-center gap-3 rounded-lg border border-accent/40 bg-bg-elevated px-6 py-14 text-center"
                      >
                        <Loader2 className="size-6 animate-spin text-accent" aria-hidden="true" />
                        <p className="text-sm font-medium text-text-primary">
                          Uploading {file?.name}&hellip;
                        </p>
                        <IndeterminateBar className="w-40" />
                      </motion.div>
                    ) : uploadStage === "error" ? (
                      <motion.div
                        key="error"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="flex flex-col items-center justify-center gap-3 rounded-lg border border-danger/40 bg-danger-soft px-6 py-14 text-center"
                      >
                        <XCircle className="size-6 text-danger" aria-hidden="true" />
                        <p className="text-sm font-medium text-text-primary">Upload failed</p>
                        <p className="max-w-sm text-xs text-danger">{uploadError}</p>
                        <Button size="sm" variant="secondary" onClick={resetUpload}>
                          Try again
                        </Button>
                      </motion.div>
                    ) : (
                      <motion.div
                        key="empty"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onDragOver={(e) => {
                          e.preventDefault();
                          setDragActive(true);
                        }}
                        onDragLeave={() => setDragActive(false)}
                        onDrop={handleDrop}
                        onClick={() => fileInputRef.current?.click()}
                        className={cn(
                          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-14 text-center transition-colors",
                          dragActive
                            ? "border-accent bg-accent-soft/40 scale-[1.01]"
                            : "border-border-strong bg-bg-elevated hover:border-accent/50",
                        )}
                      >
                        <motion.div
                          animate={
                            dragActive
                              ? { y: [-2, 2, -2] }
                              : { y: 0 }
                          }
                          transition={{ repeat: dragActive ? Infinity : 0, duration: 1.1, ease: "easeInOut" }}
                          className="flex size-12 items-center justify-center rounded-full border border-accent/30 bg-accent-soft"
                        >
                          <UploadCloud className="size-5 text-accent" aria-hidden="true" />
                        </motion.div>
                        <p className="text-sm font-medium text-text-primary">
                          {dragActive ? "Drop to upload" : "Drag & drop imagery, or click to browse"}
                        </p>
                        <p className="text-xs text-text-muted">JPG, PNG, WEBP, TIFF supported</p>
                      </motion.div>
                    )}
                  </AnimatePresence>
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
                >
                  <p className="mb-3 text-xs text-text-muted">
                    Draw a rectangle to define your AOI. Satellite search will connect to
                    Copernicus Data Space in Phase 5 — this map uses mock tiles/data only.
                  </p>
                  <AOIMap onAoiChange={setAoi} />
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
                        "relative flex-1 overflow-hidden rounded-lg border px-3 py-2 text-sm font-medium transition-colors",
                        scaleFactor === factor
                          ? "border-accent/50 text-accent"
                          : "border-border-strong text-text-secondary hover:text-text-primary",
                      )}
                    >
                      {scaleFactor === factor && (
                        <motion.span
                          layoutId="scale-factor-indicator"
                          transition={{ type: "spring", stiffness: 500, damping: 34 }}
                          className="absolute inset-0 bg-accent-soft"
                        />
                      )}
                      <span className="relative">{factor}x</span>
                    </button>
                  ))}
                </div>
              </div>

              {submitError && (
                <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-xs text-danger">
                  <XCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                  {submitError}
                </div>
              )}

              <Button
                onClick={() => setConfirmOpen(true)}
                disabled={!canSubmit}
                loading={submitting}
                className="mt-2 w-full"
              >
                Run Analysis
              </Button>

              {canSubmit && (
                <button
                  onClick={() => runAnalysis(true)}
                  disabled={submitting}
                  className="text-center text-xs text-text-muted underline-offset-2 hover:text-danger hover:underline disabled:opacity-50"
                >
                  Simulate failure (demo)
                </button>
              )}
            </div>
          </Card>
        </div>
      </div>

      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Confirm analysis"
        description="Review the details below before running the pipeline."
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleConfirmRun}>Confirm & Run</Button>
          </>
        }
      >
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-text-secondary">Name</dt>
            <dd className="text-text-primary">{jobName || "—"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-text-secondary">Source</dt>
            <dd className="text-text-primary">
              {sourceTab === "upload" ? file?.name ?? "—" : "AOI rectangle"}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-text-secondary">Scale factor</dt>
            <dd className="text-text-primary">{scaleFactor}x</dd>
          </div>
        </dl>
      </Modal>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
