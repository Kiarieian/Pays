import React, { useState, useEffect, useRef } from "react";
import {
  Smartphone,
  CheckCircle2,
  XCircle,
  Loader2,
  ArrowRight,
  Wifi,
  Battery,
  Signal,
} from "lucide-react";
import api, { ApiError } from "../Api/api";

/* ---- Phone Animation ---- */
function PhoneScreen({ stage, phone, amount, receipt }) {
  const promptText = `M-PESA\nConfirm to pay\nKSh ${amount || "0"}\nto KIARIE STR\n\nEnter PIN:`;
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (stage !== "prompt") { setTyped(""); return; }
    let i = 0;
    const t = setInterval(() => {
      i++;
      setTyped(promptText.slice(0, i));
      if (i >= promptText.length) clearInterval(t);
    }, 18);
    return () => clearInterval(t);
  }, [stage]);

  const bg = {
    idle: "var(--bg-raised)",
    dialing: "var(--bg-raised)",
    prompt: "#0a1a0a",
    "typing-pin": "#0a1a0a",
    confirming: "#0a1a0a",
    success: "var(--green-bg)",
    failed: "var(--red-bg)",
  }[stage] || "var(--bg-raised)";

  const textColor = ["prompt", "typing-pin", "confirming"].includes(stage) ? "#a3e635" : "var(--text)";

  return (
    <div className="w-[220px] mx-auto select-none">
      <div style={{ borderRadius: "24px", padding: "10px", background: "var(--bg-active)", border: "1px solid var(--border)" }}>
        <div style={{ borderRadius: "18px", overflow: "hidden", background: bg, aspectRatio: "9/17", position: "relative", transition: "background 0.3s" }}>
          {/* Status bar */}
          <div className="flex items-center justify-between" style={{ padding: "var(--space-1) var(--space-3)", fontSize: "9px", color: ["prompt", "typing-pin", "confirming"].includes(stage) ? "#a3e63580" : "var(--text-muted)" }}>
            <span className="mono">9:41</span>
            <div className="flex items-center" style={{ gap: "2px" }}>
              <Signal size={8} />
              <Wifi size={8} />
              <Battery size={9} />
            </div>
          </div>
          <div style={{ position: "absolute", top: 0, left: "50%", transform: "translateX(-50%)", width: "60px", height: "14px", background: "var(--bg-active)", borderRadius: "0 0 10px 10px" }} />

          {/* Content */}
          <div className="flex items-center justify-center" style={{ padding: "var(--space-4) var(--space-3) var(--space-6)", height: "calc(100% - 24px)" }}>
            {stage === "idle" && (
              <div className="text-center">
                <div className="flex items-center justify-center" style={{ width: "40px", height: "40px", margin: "0 auto var(--space-2)", background: "var(--green-bg)", borderRadius: "var(--radius-lg)" }}>
                  <Smartphone size={18} className="text-success" />
                </div>
                <p className="mono text-muted" style={{ fontSize: "10px" }}>Waiting...</p>
              </div>
            )}

            {stage === "dialing" && (
              <div className="text-center">
                <Loader2 className="animate-spin mx-auto" style={{ marginBottom: "var(--space-2)", color: "var(--green)" }} size={22} />
                <p className="mono" style={{ fontSize: "10px", color: "var(--text-secondary)" }}>
                  Sending to<br />
                  <span className="text-success">{phone || "—"}</span>
                </p>
              </div>
            )}

            {["prompt", "typing-pin", "confirming"].includes(stage) && (
              <div
                className="w-full rounded-md whitespace-pre-wrap"
                style={{ padding: "var(--space-3)", fontSize: "10px", lineHeight: 1.5, fontFamily: "var(--font-mono)", color: "#a3e635", border: "1px solid #16a34a40", minHeight: "90px" }}
              >
                {typed}<span className="animate-pulse">▌</span>
                {stage === "typing-pin" && (
                  <div className="flex justify-center" style={{ gap: "4px", marginTop: "var(--space-2)" }}>
                    {[0, 1, 2, 3].map((i) => (
                      <span key={i} className="animate-pulse" style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#a3e635", animationDelay: `${i * 0.15}s` }} />
                    ))}
                  </div>
                )}
                {stage === "confirming" && (
                  <p style={{ marginTop: "6px", fontSize: "9px", color: "#a3e63580" }}>Confirming...</p>
                )}
              </div>
            )}

            {stage === "success" && (
              <div className="text-center">
                <CheckCircle2 size={32} className="text-success mx-auto" style={{ marginBottom: "var(--space-2)" }} />
                <p className="font-semibold text-success" style={{ fontSize: "var(--text-sm)" }}>Paid</p>
                <p className="mono text-muted" style={{ fontSize: "9px", marginTop: "var(--space-1)" }}>{receipt || "—"}</p>
              </div>
            )}

            {stage === "failed" && (
              <div className="text-center">
                <XCircle size={32} className="text-error mx-auto" style={{ marginBottom: "var(--space-2)" }} />
                <p className="font-semibold text-error" style={{ fontSize: "var(--text-sm)" }}>Failed</p>
                <p className="text-muted" style={{ fontSize: "9px", marginTop: "var(--space-1)" }}>Cancelled or timed out</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---- Payments Page ---- */
export default function Payments() {
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [stage, setStage] = useState("idle");
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState("");
  const pollRef = useRef(null);

  const validPhone = /^2547\d{8}$|^2541\d{8}$/.test(phone);
  const validAmount = Number(amount) > 0;
  const busy = ["dialing", "prompt", "typing-pin", "confirming"].includes(stage);
  const isProcessing = busy;
  const isDone = stage === "success" || stage === "failed";

  const stopPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };
  useEffect(() => () => stopPoll(), []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!validPhone) { setError("Enter a valid Safaricom number (2547XXXXXXXX)"); return; }
    if (!validAmount) { setError("Enter an amount greater than 0"); return; }

    setStage("dialing");
    try {
      const data = await api.pay({ phone, amount: Number(amount) });
      setTimeout(() => setStage("prompt"), 600);
      setTimeout(() => setStage("typing-pin"), 2400);
      setTimeout(() => setStage("confirming"), 4200);

      const checkoutId = data.checkout_id;
      pollRef.current = setInterval(async () => {
        try {
          const list = await api.listPayments();
          const match = list.find((p) => p.checkout_request_id === checkoutId);
          if (match && match.status !== "PENDING") {
            stopPoll();
            if (match.status === "SUCCESS") {
              setReceipt(match.mpesa_receipt || "");
              setStage("success");
            } else {
              setStage("failed");
            }
          }
        } catch { /* keep polling */ }
      }, 2500);
      setTimeout(() => {
        stopPoll();
        setStage((s) => (["confirming", "prompt", "typing-pin"].includes(s) ? "failed" : s));
      }, 45000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach payment service.");
      setStage("idle");
    }
  };

  const reset = () => {
    stopPoll();
    setStage("idle");
    setReceipt("");
    setPhone("");
    setAmount("");
    setReference("");
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-header-content">
          <h1 className="page-title">Payments</h1>
          <p className="page-description">
            Collect a payment from your customer.
          </p>
        </div>
      </div>

      <div className="payment-layout">
        <div className="payment-form">
          <form onSubmit={handleSubmit}>
            <div className="payment-form-section">
              <div className="payment-method">
                <div className="payment-method-icon">
                  <Smartphone size={18} />
                </div>
                <div className="payment-method-content">
                  <div className="payment-method-title">STK Push</div>
                  <div className="payment-method-description">Customer receives a prompt on their phone</div>
                </div>
                <div className="payment-method-check">
                  <CheckCircle2 size={20} />
                </div>
              </div>

              <div className="payment-fields">
                <div className="form-field payment-fields-full">
                  <label className="form-label">Customer phone</label>
                  <div className="phone-input-wrapper">
                    <span className="phone-prefix">+254</span>
                    <input
                      type="tel"
                      className="input phone-input"
                      placeholder="7XX XXX XXX"
                      value={phone.replace(/^254/, "")}
                      disabled={busy}
                      onChange={(e) => setPhone("254" + e.target.value.replace(/[^\d]/g, "").slice(0, 9))}
                    />
                  </div>
                </div>

                <div className="form-field">
                  <label className="form-label">Amount</label>
                  <div className="amount-input-wrapper">
                    <span className="amount-prefix">KSh</span>
                    <input
                      type="number"
                      min="1"
                      className="input amount-input"
                      placeholder="0"
                      value={amount}
                      disabled={busy}
                      onChange={(e) => setAmount(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-field">
                  <label className="form-label">
                    Reference <span className="form-label-optional">(optional)</span>
                  </label>
                  <input
                    type="text"
                    className="input"
                    placeholder="e.g. Order #123"
                    value={reference}
                    disabled={busy}
                    onChange={(e) => setReference(e.target.value)}
                  />
                </div>
              </div>
            </div>

            {error && (
              <div className="alert alert-error" style={{ marginTop: "var(--space-4)" }}>
                <div className="alert-content">
                  <div className="alert-message">{error}</div>
                </div>
              </div>
            )}

            <div className="flex" style={{ gap: "var(--space-3)", marginTop: "var(--space-5)" }}>
              <button
                type="submit"
                disabled={busy}
                className="btn btn-primary payment-submit"
              >
                {busy ? (
                  <><Loader2 size={15} className="spinner" /> Processing...</>
                ) : (
                  <>Request Payment <ArrowRight size={15} /></>
                )}
              </button>
              {isDone && (
                <button
                  type="button"
                  onClick={reset}
                  className="btn btn-secondary"
                >
                  New
                </button>
              )}
            </div>
          </form>
        </div>

        <div className="payment-summary">
          <div className="card card-padded">
            {isProcessing || isDone ? (
              <>
                <p className="text-muted font-semibold" style={{ fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-4)" }}>
                  Customer screen
                </p>
                <PhoneScreen stage={stage} phone={phone} amount={amount} receipt={receipt} />
              </>
            ) : (
              <>
                <p className="text-muted font-semibold" style={{ fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-4)" }}>
                  Payment summary
                </p>
                <div className="summary-list">
                  {[
                    { label: "Amount", value: validAmount ? `KSh ${Number(amount).toLocaleString()}` : "—" },
                    { label: "Method", value: "M-Pesa STK" },
                    { label: "Customer", value: phone ? `+${phone}` : "—" },
                    { label: "Reference", value: reference || "—" },
                    { label: "Status", value: "Ready" },
                  ].map((row) => (
                    <div key={row.label} className="summary-row">
                      <span className="summary-label">{row.label}</span>
                      <span className="summary-value mono">{row.value}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
