import { motion } from "framer-motion";
import { Activity, CheckCircle2, Gauge, Layers, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getResult, listProcessingJobs } from "../api/client";
import PageHeader from "../components/layout/PageHeader";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import ErrorState from "../components/ui/ErrorState";
import MetricCard from "../components/ui/MetricCard";
import { SkeletonCard, SkeletonRow } from "../components/ui/Skeleton";
import StatusBadge from "../components/ui/StatusBadge";
import { toBadgeStatus } from "../lib/jobStatus";

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
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [jobs, setJobs] = useState([]);
  // job_id -> { psnr, ssim, lpips } for completed jobs, fetched separately
  // since the list endpoint returns job records only, not metrics.
  const [metricsByJob, setMetricsByJob] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const jobList = await listProcessingJobs({ limit: 50 });
      setJobs(jobList);

      const completed = jobList.filter((j) => j.status === "completed");
      const entries = await Promise.all(
        completed.map(async (j) => {
          try {
            const result = await getResult(j.job_id);
            return [j.job_id, result];
          } catch {
            return [j.job_id, null];
          }
        }),
      );
      setMetricsByJob(Object.fromEntries(entries.filter(([, v]) => v)));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const completed = jobs.filter((j) => j.status === "completed").length;
  const processing = jobs.filter((j) => j.status === "processing" || j.status === "queued").length;
  const psnrValues = Object.values(metricsByJob)
    .map((r) => r.psnr)
    .filter((v) => typeof v === "number");
  const avgPsnr =
    psnrValues.length > 0
      ? Number((psnrValues.reduce((sum, v) => sum + v, 0) / psnrValues.length).toFixed(1))
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

      {error ? (
        <ErrorState
          title="Couldn't load analyses"
          description={
            error.isNetworkError
              ? "Unable to reach the backend. Make sure it's running, then retry."
              : error.message
          }
          onRetry={load}
          retryLabel="Retry"
        />
      ) : (
        <>
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
                onAction={() => navigate("/process")}
              />
            ) : (
              <motion.div
                variants={listVariants}
                initial="hidden"
                animate="visible"
                className="flex flex-col gap-3"
              >
                {jobs.map((job) => {
                  const metrics = metricsByJob[job.job_id];
                  return (
                    <motion.div key={job.job_id} variants={itemVariants}>
                      <Card
                        as={Link}
                        to={`/results/${job.job_id}`}
                        interactive
                        className="flex flex-col gap-3 hover:border-accent/40 hover:bg-surface-hover sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div>
                          <p className="font-medium text-text-primary">{job.analysis_name}</p>
                          <p className="mt-1 text-xs text-text-muted">
                            {job.job_id.slice(0, 8)} &middot; {formatDate(job.created_at)}{" "}
                            &middot; {job.scale_factor}x scale
                          </p>
                        </div>
                        <div className="flex items-center gap-4">
                          {metrics && (
                            <span className="hidden text-xs text-text-secondary sm:inline">
                              PSNR {metrics.psnr} dB
                            </span>
                          )}
                          <StatusBadge status={toBadgeStatus(job.status)} />
                        </div>
                      </Card>
                    </motion.div>
                  );
                })}
              </motion.div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
