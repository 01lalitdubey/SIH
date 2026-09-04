// Centralized API client — every backend call in the app goes through here
// instead of scattering fetch() calls across components.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(message, { status, detail } = {}) {
    super(message);
    this.name = "ApiError";
    // `status` is undefined for network-level failures (backend unreachable,
    // timeout) as opposed to a real HTTP error response.
    this.status = status;
    this.detail = detail;
  }

  get isNetworkError() {
    return this.status === undefined;
  }
}

async function request(path, { method = "GET", body, isFormData = false, signal } = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: isFormData || !body ? undefined : { "Content-Type": "application/json" },
      body: isFormData ? body : body ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError("Unable to reach the server. Is the backend running?");
  }

  if (!response.ok) {
    let detail = response.statusText || `Request failed with status ${response.status}`;
    try {
      const data = await response.json();
      if (data?.detail) detail = data.detail;
    } catch {
      // Response body wasn't JSON — fall back to statusText already set above.
    }
    // FastAPI validation errors return `detail` as an array of issues rather
    // than a string; flatten that into something readable.
    const message = Array.isArray(detail)
      ? detail.map((d) => d.msg ?? JSON.stringify(d)).join("; ")
      : String(detail);
    throw new ApiError(message, { status: response.status, detail });
  }

  if (response.status === 204) return null;
  return response.json();
}

export function checkHealth(options) {
  return request("/health", options);
}

// --- Images -----------------------------------------------------------

export function uploadImage(file, options = {}) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/images/upload", {
    method: "POST",
    body: formData,
    isFormData: true,
    ...options,
  });
}

export function getImages(params = {}, options = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`/images${qs ? `?${qs}` : ""}`, options);
}

export function getImage(imageId, options = {}) {
  return request(`/images/${imageId}`, options);
}

export function getImageFileUrl(imageId) {
  return `${API_BASE_URL}/images/${imageId}/file`;
}

// --- Processing ---------------------------------------------------------

export function createProcessingJob(payload, options = {}) {
  return request("/process", { method: "POST", body: payload, ...options });
}

export function listProcessingJobs(params = {}, options = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`/process${qs ? `?${qs}` : ""}`, options);
}

export function getProcessingStatus(jobId, options = {}) {
  return request(`/process/${jobId}`, options);
}

// --- Results --------------------------------------------------------------

export function getResult(jobId, options = {}) {
  return request(`/results/${jobId}`, options);
}

export function getResultFileUrl(jobId) {
  return `${API_BASE_URL}/results/${jobId}/file`;
}
