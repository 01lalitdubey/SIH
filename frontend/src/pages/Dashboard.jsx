import { motion } from "framer-motion";
import { Activity, CheckCircle2, Gauge, Layers, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import MetricCard from "../components/ui/MetricCard";
import { SkeletonCard, SkeletonRow } from "../components/ui/Skeleton";
import StatusBadge from "../components/ui/StatusBadge";
import { MOCK_JOBS } from "../data/mockJobs";

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

const listVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" } },
};

export default function Dashboard() {
  // MOCK/TEMPORARY — simulated fetch delay + local data; replaced by a real
  // API call in Phase 4.
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 550);
    return () => clearTimeout(timer);
  }, []);

  const jobs = MOCK_JOBS;
  const completed = jobs.filter((j) => j.status === "completed").length;
  const processing = jobs.filter((j) => j.status === "processing").length;
  const jobsWithMetrics = jobs.filter((j) => j.metrics);
  const avgPsnr =
    jobsWithMetrics.length > 0
      ? Number(
          (
            jobsWithMetrics.reduce((sum, j) => sum + j.metrics.psnr, 0) /
            jobsWithMetrics.length
          ).toFixed(1),
        )
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

      {loading ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : (
        <motion.div
          variants={listVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-2 gap-4 lg:grid-cols-4"
        >
          <motion.div variants={itemVariants}>
            <MetricCard label="Total Analyses" value={jobs.length} icon={Layers} />
          </motion.div>
          <motion.div variants={itemVariants}>
            <MetricCard label="Completed" value={completed} icon={CheckCircle2} />
          </motion.div>
          <motion.div variants={itemVariants}>
            <MetricCard label="Processing" value={processing} icon={Activity} />
          </motion.div>
          <motion.div variants={itemVariants}>
            <MetricCard
              label="Avg. PSNR"
              value={avgPsnr}
              decimals={1}
              unit="dB"
              icon={Gauge}
              hint="Mocked until Phase 7"
            />
          </motion.div>
        </motion.div>
      )}

      <div className="mt-8">
        <h2 className="mb-4 font-display text-sm font-semibold text-text-secondary">
          Recent Analyses
        </h2>

        {loading ? (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <SkeletonRow key={i} />
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <EmptyState
            title="No analyses yet"
            description="Start a new analysis to see it appear here."
            actionLabel="New Analysis"
          />
        ) : (
          <motion.div
            variants={listVariants}
            initial="hidden"
            animate="visible"
            className="flex flex-col gap-3"
          >
            {jobs.map((job) => (
              <motion.div key={job.id} variants={itemVariants}>
                <Card
                  as={Link}
                  to={`/results/${job.id}`}
                  interactive
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
          </motion.div>
        )}
      </div>
    </div>
  );
}
