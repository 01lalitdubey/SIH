import { useEffect, useRef, useState } from "react";
import { getProcessingStatus } from "../api/client";
import { TERMINAL_STATUSES } from "../lib/jobStatus";

const POLL_INTERVAL_MS = 1200;
// Transient network hiccups get retried; this many in a row means the
// backend is genuinely unreachable, so stop and surface an error instead of
// polling forever.
const MAX_CONSECUTIVE_ERRORS = 4;

/**
 * Polls GET /process/{jobId} — the backend is the sole source of truth for
 * status/progress/stage, never a frontend timer. Stops automatically once
 * the job reaches a terminal status (completed/failed) or after repeated
 * network failures.
 */
export function useProcessingPoll(jobId) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setJob(null);
    setError(null);
    if (!jobId) return undefined;

    let cancelled = false;
    let timeoutId;
    let consecutiveErrors = 0;

    async function poll() {
      try {
        const data = await getProcessingStatus(jobId);
        if (cancelled) return;
        consecutiveErrors = 0;
        setJob(data);
        if (!TERMINAL_STATUSES.has(data.status)) {
          timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (cancelled) return;

        if (err.status === 404) {
          setError(err); // invalid/unknown job id — no point retrying
          return;
        }

        consecutiveErrors += 1;
        if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
          setError(err); // backend unavailable after repeated attempts
          return;
        }
        timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    poll();

    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [jobId]);

  return { job, error };
}
