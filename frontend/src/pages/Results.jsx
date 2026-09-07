import { motion } from "framer-motion";
import { CheckCircle2, Download, Gauge, Layers, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getImageFileUrl, getProcessingStatus, getResult, getResultFileUrl } from "../api/client";
import PageHeader from "../components/layout/PageHeader";
import CompareSlider from "../components/results/CompareSlider";
import Button from "../components/ui/Button";
import Card, { CardHeader } from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import ErrorState from "../components/ui/ErrorState";
import LoadingState from "../components/ui/LoadingState";
import MetricCard from "../components/ui/MetricCard";
import StatusBadge from "../components/ui/StatusBadge";
import {
  classifyFailure,
  displayModelName,
  displaySatelliteProvider,
  toBadgeStatus,
} from "../lib/jobStatus";

const listVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" } },
};

export default function Results() {
  const { jobId } = useParams();
  const navigate = useNavigate();

  // "loading" | "error" | "ready"
  const [phase, setPhase] = useState("loading");
  const [job, setJob] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setPhase("loading");
    setError(null);
    try {
      const jobData = await getProcessingStatus(jobId);
      setJob(jobData);

      if (jobData.status === "completed") {
        const resultData = await getResult(jobId);
        setResult(resultData);
      }
      setPhase("ready");
    } catch (err) {
      setJob(null);
      setResult(null);
      setError(err);
      setPhase("error");
    }
  }, [jobId]);

  useEffect(() => {
    load();
  }, [load]);

  if (phase === "loading") {
    return <LoadingState label="Loading analysis" />;
  }

  if (phase === "error") {
    if (error?.status === 404) {
      return (
        <ErrorState
          title="Analysis not found"
          description={`No analysis with id "${jobId}" exists.`}
          onRetry={() => navigate("/dashboard")}
          retryLabel="Back to Dashboard"
        />
      );
    }
    return (
      <ErrorState
        title="Couldn't load this analysis"
        description={
          error?.isNetworkError
            ? "Unable to reach the backend. Make sure it's running, then retry."
            : error?.message || "An unexpected error occurred."
        }
        onRetry={load}
        retryLabel="Retry"
      />
    );
  }

  return (
    <div>
      <PageHeader
        title={job.analysis_name}
        description={`${job.job_id} · ${job.scale_factor}x scale factor`}
        action={<StatusBadge status={toBadgeStatus(job.status)} />}
      />

      {job.status === "failed" ? (
        <ErrorState
          title={classifyFailure(job)?.title ?? "Analysis Failed"}
          description={
            job.error_message || "This job failed during processing. Try running a new analysis."
          }
          onRetry={() => navigate("/process")}
          retryLabel="New Analysis"
        />
      ) : job.status === "queued" || job.status === "processing" ? (
        <EmptyState
          icon={Sparkles}
          title="Still processing"
          description="This analysis is still running. Results will appear here once it completes."
          actionLabel="Back to Dashboard"
          onAction={() => navigate("/dashboard")}
        />
      ) : (
        <motion.div variants={listVariants} initial="hidden" animate="visible">
          <motion.div
            variants={itemVariants}
            className="mb-6 flex items-center gap-2 rounded-lg border border-success/30 bg-success-soft px-4 py-3 text-sm text-success"
          >
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 400, damping: 15, delay: 0.15 }}
            >
              <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
            </motion.span>
            Processing complete — result ready for review.
          </motion.div>

          <motion.div variants={itemVariants}>
            <CompareSlider
              beforeSrc={job.image_id ? getImageFileUrl(job.image_id) : undefined}
              afterSrc={result?.output_path ? getResultFileUrl(job.job_id) : undefined}
            />
            <p className="mt-2 text-center text-xs text-text-muted">
              Drag the handle to compare before and after
            </p>
            {job.satellite_scene && (
              <p className="mt-1 text-center text-xs text-text-muted">
                Satellite source: {displaySatelliteProvider(job.satellite_scene.provider)}
                {job.satellite_scene.cloud_cover != null &&
                  ` · ${job.satellite_scene.cloud_cover.toFixed(1)}% cloud cover`}
              </p>
            )}
          </motion.div>

          <motion.div variants={itemVariants} className="mt-8">
            <CardHeader
              title="Evaluation Metrics"
              subtitle={
                result?.is_mock
                  ? "Simulated values — for demonstration only"
                  : result?.metrics_available
                    ? "Computed against reference imagery"
                    : "Quality metrics are available for validated reference imagery"
              }
              action={
                result && (
                  <span className="rounded-full border border-border-strong bg-bg-elevated px-2.5 py-1 text-xs font-medium text-text-secondary">
                    {result.is_mock
                      ? "Mock pipeline"
                      : `${displayModelName(result.model_name)} · AI-enhanced · ${result.device ?? "cpu"}`}
                  </span>
                )
              }
            />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <MetricCard
                label="PSNR"
                value={result?.psnr}
                decimals={1}
                unit="dB"
                icon={Gauge}
                ringPercent={result?.psnr ? Math.min(100, (result.psnr / 50) * 100) : undefined}
              />
              <MetricCard
                label="SSIM"
                value={result?.ssim}
                decimals={3}
                icon={Layers}
                ringPercent={result?.ssim ? result.ssim * 100 : undefined}
              />
              <MetricCard
                label="LPIPS"
                value={result?.lpips}
                decimals={3}
                icon={Sparkles}
                ringPercent={result?.lpips ? (1 - result.lpips) * 100 : undefined}
              />
            </div>
            {result && !result.is_mock && !result.metrics_available && (
              <p className="mt-3 text-xs text-text-muted">
                Metrics unavailable for this inference — there is no ground-truth
                high-resolution image to compare the model&apos;s predicted output against.
              </p>
            )}
          </motion.div>

          <motion.div variants={itemVariants}>
            <Card className="mt-6 flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
              <div>
                <p className="text-sm font-medium text-text-primary">Download result</p>
                <p className="text-xs text-text-muted">
                  {result?.output_path
                    ? "GeoTIFF export lands in a later phase — PNG preview only for now."
                    : "No output file for this job (AOI-only jobs don't generate one yet)."}
                </p>
              </div>
              <Button variant="secondary" icon={Download} disabled>
                Download GeoTIFF
              </Button>
            </Card>
          </motion.div>
        </motion.div>
      )}
    </div>
  );
}
