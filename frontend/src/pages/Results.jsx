import { Download, Gauge, Layers, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import Button from "../components/ui/Button";
import Card, { CardHeader } from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import ErrorState from "../components/ui/ErrorState";
import ImageContainer from "../components/ui/ImageContainer";
import LoadingState from "../components/ui/LoadingState";
import MetricCard from "../components/ui/MetricCard";
import StatusBadge from "../components/ui/StatusBadge";
import { getMockJobById } from "../data/mockJobs";

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
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <ImageContainer label="Before — Medium Resolution" aspect="aspect-video" />
            <ImageContainer label="After — Super-Resolved (MOCK)" aspect="aspect-video" />
          </div>

          <div className="mt-6">
            <CardHeader title="Evaluation Metrics" subtitle="Mocked values — real in Phase 7" />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <MetricCard label="PSNR" value={job.metrics?.psnr} unit="dB" icon={Gauge} />
              <MetricCard label="SSIM" value={job.metrics?.ssim} icon={Layers} />
              <MetricCard label="LPIPS" value={job.metrics?.lpips} icon={Sparkles} />
            </div>
          </div>

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
        </>
      )}
    </div>
  );
}
