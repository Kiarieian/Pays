
const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  "http://localhost:8000";

const MERCHANT_API_KEY =
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_MERCHANT_API_KEY) ||
  "";

class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

async function request(path, { method = "GET", body, headers = {}, auth = false } = {}) {
  const finalHeaders = { ...headers };
  let finalBody = body;

  if (body !== undefined) {
    finalHeaders["Content-Type"] = "application/json";
    finalBody = JSON.stringify(body);
  }

  if (auth) {
    finalHeaders["X-API-Key"] = MERCHANT_API_KEY;
  }

  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: finalHeaders,
      body: finalBody,
    });
  } catch (err) {
    // Network failure / backend not running / CORS block
    throw new ApiError(
      `Could not reach the backend at ${API_BASE_URL}. Is the server running and CORS enabled?`,
      0,
      null
    );
  }

  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    const message =
      (data && (data.detail || data.message)) || `Request failed with status ${res.status}`;
    throw new ApiError(message, res.status, data);
  }

  return data;
}

export const api = {
  baseUrl: API_BASE_URL,

  // GET /  — health check
  ping: () => request("/"),

  // GET /token — fetch a Daraja access token (debug route)
  getToken: () => request("/token"),

  // GET /payments — list all payments
  listPayments: () => request("/payments"),

  // POST /pay — trigger an STK push. Requires merchant API key.
  pay: ({ phone, amount }) =>
    request("/pay", {
      method: "POST",
      body: { phone, amount },
      auth: true,
    }),

  // GET /generate_qr — generate a scan-to-pay QR code
  generateQr: ({ amount }) => request(`/generate_qr?amount=${encodeURIComponent(amount)}`),
};

export { ApiError, API_BASE_URL, MERCHANT_API_KEY };
export default api;