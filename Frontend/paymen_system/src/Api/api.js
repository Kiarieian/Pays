
const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  "http://localhost:8000";

let _sessionToken = null;

export function setSessionToken(token) {
  _sessionToken = token;
}

export function getSessionToken() {
  return _sessionToken;
}

export function clearSessionToken() {
  _sessionToken = null;
}

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

  if (auth && _sessionToken) {
    finalHeaders["Authorization"] = `Bearer ${_sessionToken}`;
  }

  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: finalHeaders,
      body: finalBody,
    });
  } catch (err) {
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

  ping: () => request("/"),

  login: (email, password) =>
    request("/auth/login", {
      method: "POST",
      body: { email, password },
    }).then((data) => {
      setSessionToken(data.session_token);
      return data;
    }),

  logout: () =>
    request("/auth/logout", { method: "POST", auth: true })
      .finally(() => clearSessionToken()),

  listPayments: () =>
    request("/payments", { method: "GET", auth: true }),

  listUsage: () =>
    request("/usage", { method: "GET", auth: true }),

  getProfile: () =>
    request("/merchants/me", { method: "GET", auth: true }),

  pay: ({ phone, amount, account_reference }) =>
    request("/pay", {
      method: "POST",
      body: { phone, amount: Number(amount), account_reference },
      auth: true,
    }),

  generateQr: ({ amount, account_reference, trx_code = "BG" }) =>
    request("/generate_qr", {
      method: "POST",
      body: { amount: Number(amount), account_reference, trx_code },
      auth: true,
    }),

  disburse: ({ phone, amount, remarks }) =>
    request("/disburse", {
      method: "POST",
      body: { phone, amount: Number(amount), remarks },
      auth: true,
    }),
};

export { ApiError, API_BASE_URL };
export default api;
