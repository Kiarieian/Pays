import React, { useState, useEffect } from "react";
import { Copy, Check, Circle } from "lucide-react";
import api from "../Api/api";

const ENDPOINTS = [
  {
    method: "POST",
    path: "/pay",
    desc: "Initiate an STK Push payment",
    body: '{\n  "phone": "2547XXXXXXXX",\n  "amount": 100\n}',
    response: '{\n  "checkout_id": "ws_CO_...",\n  "message": "STK push sent"\n}',
  },
  {
    method: "POST",
    path: "/generate_qr",
    desc: "Generate an M-Pesa QR payment",
    body: '{\n  "amount": 100,\n  "account_reference": "Order-123"\n}',
    response: '{\n  "qr_code_base64": "iVBOR...",\n  "account_reference": "Order-123"\n}',
  },
  {
    method: "GET",
    path: "/payments",
    desc: "Retrieve transactions",
    response: '[\n  {\n    "id": 1,\n    "phone": "2547XXXXXXXX",\n    "amount": 100,\n    "status": "SUCCESS",\n    "mpesa_receipt": "QHK3F...",\n    "created_at": "2026-09-02T10:30:00"\n  }\n]',
  },
  {
    method: "GET",
    path: "/usage",
    desc: "View API usage",
    response: '{\n  "recent_requests": 42,\n  "success_rate": 0.95,\n  "requests": [...]\n}',
  },
];

function CopyBtn({ text }) {
  const [ok, setOk] = useState(false);
  return (
    <button
      className="btn btn-ghost"
      style={{ minHeight: "28px", padding: "0 var(--space-2)" }}
      onClick={() => { navigator.clipboard.writeText(text); setOk(true); setTimeout(() => setOk(false), 1500); }}
    >
      {ok ? <Check size={13} className="text-success" /> : <Copy size={13} />}
    </button>
  );
}

export default function APIIntegration() {
  const [usage, setUsage] = useState(null);
  const baseUrl = api.baseUrl || "http://localhost:8000";

  useEffect(() => { api.listUsage().then(setUsage).catch(() => {}); }, []);

  return (
    <div>
      <div className="page-header">
        <div className="page-header-content">
          <h1 className="page-title">API Integration</h1>
          <p className="page-description">
            Connect any website or application to your payment infrastructure.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap" style={{ gap: "var(--space-4)", marginBottom: "var(--space-8)" }}>
        <div className="flex items-center card card-padded" style={{ padding: "var(--space-3) var(--space-4)", gap: "var(--space-2)" }}>
          <Circle size={8} fill="var(--green)" style={{ color: "var(--green)" }} />
          <span className="text-secondary" style={{ fontSize: "var(--text-sm)" }}>API Connected</span>
        </div>
        <div className="flex items-center card card-padded" style={{ padding: "var(--space-3) var(--space-4)", gap: "var(--space-2)" }}>
          <span className="text-muted" style={{ fontSize: "var(--text-xs)" }}>Base URL</span>
          <code style={{ fontSize: "var(--text-sm)" }}>{baseUrl}</code>
          <CopyBtn text={baseUrl} />
        </div>
        {usage && (
          <div className="flex items-center card card-padded" style={{ padding: "var(--space-3) var(--space-4)", gap: "var(--space-2)" }}>
            <span className="text-muted" style={{ fontSize: "var(--text-xs)" }}>Usage</span>
            <span className="mono font-medium" style={{ fontSize: "var(--text-sm)" }}>
              {usage.recent_requests || 0} requests
            </span>
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: "var(--space-8)" }}>
        <div className="card-body">
          <p className="text-muted font-semibold" style={{ fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "var(--space-3)" }}>
            Authentication
          </p>
          <p className="text-secondary" style={{ fontSize: "var(--text-sm)", marginBottom: "var(--space-3)" }}>
            Include your API key in the <code>X-API-Key</code> header with every request.
          </p>
          <div className="api-key-display">
            <span className="api-key-value">
              curl -H "X-API-Key: YOUR_KEY" {baseUrl}/payments
            </span>
            <CopyBtn text={`curl -H "X-API-Key: YOUR_KEY" ${baseUrl}/payments`} />
          </div>
        </div>
      </div>

      <h2 className="font-semibold" style={{ fontSize: "var(--text-md)", marginBottom: "var(--space-4)" }}>Available endpoints</h2>
      <div className="flex flex-col" style={{ gap: "var(--space-3)", marginBottom: "var(--space-10)" }}>
        {ENDPOINTS.map((ep, i) => (
          <div key={i} className="card">
            <div className="flex items-center" style={{ padding: "var(--space-3) var(--space-5)", borderBottom: "1px solid var(--border-subtle)", gap: "var(--space-3)" }}>
              <span
                className="mono font-bold"
                style={{
                  fontSize: "var(--text-xs)",
                  padding: "2px var(--space-2)",
                  borderRadius: "var(--radius-sm)",
                  background: ep.method === "GET" ? "var(--green-bg)" : "var(--blue-bg)",
                  color: ep.method === "GET" ? "var(--green)" : "var(--blue)",
                }}
              >
                {ep.method}
              </span>
              <span className="mono font-medium" style={{ fontSize: "var(--text-sm)" }}>{ep.path}</span>
              <span className="text-muted" style={{ fontSize: "var(--text-sm)", marginLeft: "var(--space-2)" }}>{ep.desc}</span>
            </div>

            <div className="grid grid-2 gap-4" style={{ padding: "var(--space-5)" }}>
              {ep.body && (
                <div>
                  <div className="flex items-center justify-between" style={{ marginBottom: "var(--space-1)" }}>
                    <span className="text-muted font-semibold" style={{ fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Request</span>
                    <CopyBtn text={ep.body} />
                  </div>
                  <pre>{ep.body}</pre>
                </div>
              )}
              <div>
                <div className="flex items-center justify-between" style={{ marginBottom: "var(--space-1)" }}>
                  <span className="text-muted font-semibold" style={{ fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Response</span>
                  <CopyBtn text={ep.response} />
                </div>
                <pre>{ep.response}</pre>
              </div>
            </div>
          </div>
        ))}
      </div>

      <h2 className="font-semibold" style={{ fontSize: "var(--text-md)", marginBottom: "var(--space-4)" }}>Example integration</h2>
      <div className="card">
        <div className="card-header" style={{ padding: "var(--space-3) var(--space-5)" }}>
          <span className="text-muted" style={{ fontSize: "var(--text-xs)" }}>JavaScript — STK Push</span>
          <CopyBtn text={`const res = await fetch("${baseUrl}/pay", {\n  method: "POST",\n  headers: {\n    "Content-Type": "application/json",\n    "X-API-Key": "YOUR_KEY"\n  },\n  body: JSON.stringify({\n    phone: "2547XXXXXXXX",\n    amount: 100\n  })\n});\nconst data = await res.json();\n// data.checkout_id → "ws_CO_..."`} />
        </div>
        <pre style={{ margin: 0 }}>
{`const res = await fetch("${baseUrl}/pay", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": "YOUR_KEY"
  },
  body: JSON.stringify({
    phone: "2547XXXXXXXX",
    amount: 100
  })
});

const data = await res.json();
// data.checkout_id → "ws_CO_..."`}
        </pre>
      </div>
    </div>
  );
}
