import { motion } from "framer-motion";
import { Activity, CheckCircle2, Gauge, Layers, Plus } from "lucide-react";
import { Link } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import MetricCard from "../components/ui/MetricCard";
import StatusBadge from "../components/ui/StatusBadge";
import { MOCK_JOBS } from "../data/mockJobs";

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function Dashboard() {
  // MOCK/TEMPORARY — replaced by a real API call in Phase 4.
  const jobs = MOCK_JOBS;
  const completed = jobs.filter((j) => j.status === "completed").length;
  const processing = jobs.filter((j) => j.status === "processing").length;
  const avgPsnr =
    jobs.filter((j) => j.metrics).length > 0
      ? (
          jobs.reduce((sum, j) => sum + (j.metrics?.psnr ?? 0), 0) /
          jobs.filter((j) => j.metrics).length
        ).toFixed(1)
      : null;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Overview of your super-resolution analyses."
        action={
          <Button as={Link} to="/process" icon={Plus}>
            New Analysis
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard label="Total Analyses" value={jobs.length} icon={Layers} />
        <MetricCard label="Completed" value={completed} icon={CheckCircle2} />
        <MetricCard label="Processing" value={processing} icon={Activity} />
        <MetricCard
          label="Avg. PSNR"
          value={avgPsnr}
          unit="dB"
          icon={Gauge}
          hint="Mocked until Phase 7"
        />
      </div>

      <div className="mt-8">
        <h2 className="mb-4 font-display text-sm font-semibold text-text-secondary">
          Recent Analyses
        </h2>

        {jobs.length === 0 ? (
          <EmptyState
            title="No analyses yet"
            description="Start a new analysis to see it appear here."
            actionLabel="New Analysis"
          />
        ) : (
          <div className="flex flex-col gap-3">
            {jobs.map((job, i) => (
              <motion.div
                key={job.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: i * 0.04 }}
              >
                <Card
                  as={Link}
                  to={`/results/${job.id}`}
                  className="flex flex-col gap-3 hover:border-accent/40 hover:bg-surface-hover sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <p className="font-medium text-text-primary">{job.name}</p>
                    <p className="mt-1 text-xs text-text-muted">
                      {job.id} &middot; {formatDate(job.createdAt)} &middot; {job.scaleFactor}x
                      scale
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    {job.metrics && (
                      <span className="hidden text-xs text-text-secondary sm:inline">
                        PSNR {job.metrics.psnr} dB
                      </span>
                    )}
                    <StatusBadge status={job.status} />
                  </div>
                </Card>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
