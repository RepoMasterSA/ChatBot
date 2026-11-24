const BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {}

function describeError(status, detail) {
  if (status === 422) {
    return "Your message could not be sent. It must be between 1 and 4,000 characters.";
  }
  if (status === 503) {
    return "All model providers are unavailable right now. Try again in a moment.";
  }
  if (typeof detail === "string" && detail) return detail;
  return `The server returned an unexpected error (${status}). Try again.`;
}

export async function sendMessage({ sessionId, message, systemPrompt, simulateFailure }) {
  const headers = { "Content-Type": "application/json" };
  if (simulateFailure) headers["X-Simulate-Failure"] = simulateFailure;

  const body = { session_id: sessionId, message };
  if (systemPrompt) body.system_prompt = systemPrompt;

  let response;
  try {
    response = await fetch(`${BASE}/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection and try again.");
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    /* non-JSON body: fall through to the generic message */
  }

  if (!response.ok) {
    throw new ApiError(describeError(response.status, data?.detail));
  }
  return data;
}
