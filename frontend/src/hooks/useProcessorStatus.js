import { useEffect, useState } from "react";
import { checkHealth } from "../api/client";

/**
 * The backend's real processor state (GET /health) — shared by every
 * component that needs to say whether real AI inference is active instead
 * of hardcoding it. Returns null until the first check resolves; stays
 * null (rather than throwing) if the backend is unreachable, since it's
 * each caller's job to decide how loudly to surface that.
 */
export function useProcessorStatus() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let cancelled = false;
    checkHealth()
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return status;
}
