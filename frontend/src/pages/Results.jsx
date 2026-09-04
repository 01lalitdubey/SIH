import { motion } from "framer-motion";
import { CheckCircle2, Download, Gauge, Layers, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import CompareSlider from "../components/results/CompareSlider";
import Button from "../components/ui/Button";
import Card, { CardHeader } from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import ErrorState from "../components/ui/ErrorState";
import LoadingState from "../components/ui/LoadingState";
import MetricCard from "../components/ui/MetricCard";
import StatusBadge from "../components/ui/StatusBadge";
import { getMockJobById } from "../data/mockJobs";

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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    // MOCK/TEMPORARY — simulates a fetch delay; replaced by a real API call in Phase 4.
    const timer = setTimeout(() => setLoading(false), 500);
    return () => clearTimeout(timer);
  }, [jobId]);

  if (loading) {
    return <LoadingState label="Loading analysis" />;
  }

  const job = getMockJobById(jobId);

  if (!job) {
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
    <div>
      <PageHeader
        title={job.name}
        description={`${job.id} · ${job.scaleFactor}x scale factor`}
        action={<StatusBadge status={job.status} />}
      />

      {job.status === "failed" ? (
        <ErrorState
          title="Analysis failed"
          description="This mock job failed during processing. Try running a new analysis."
          onRetry={() => navigate("/process")}
          retryLabel="New Analysis"
        />
      ) : job.status === "processing" ? (
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
            <CompareSlider />
            <p className="mt-2 text-center text-xs text-text-muted">
              Drag the handle to compare before and after
            </p>
          </motion.div>

          <motion.div variants={itemVariants} className="mt-8">
            <CardHeader title="Evaluation Metrics" subtitle="Mocked values — real in Phase 7" />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <MetricCard
                label="PSNR"
                value={job.metrics?.psnr}
                decimals={1}
                unit="dB"
                icon={Gauge}
                ringPercent={job.metrics ? Math.min(100, (job.metrics.psnr / 50) * 100) : undefined}
              />
              <MetricCard
                label="SSIM"
                value={job.metrics?.ssim}
                decimals={3}
                icon={Layers}
                ringPercent={job.metrics ? job.metrics.ssim * 100 : undefined}
              />
              <MetricCard
                label="LPIPS"
                value={job.metrics?.lpips}
                decimals={3}
                icon={Sparkles}
                ringPercent={job.metrics ? (1 - job.metrics.lpips) * 100 : undefined}
              />
            </div>
          </motion.div>

          <motion.div variants={itemVariants}>
            <Card className="mt-6 flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
              <div>
                <p className="text-sm font-medium text-text-primary">Download result</p>
                <p className="text-xs text-text-muted">
                  GeoTIFF export becomes available once the backend is connected.
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
