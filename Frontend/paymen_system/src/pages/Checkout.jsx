import React, { useState, useEffect, useRef } from "react";
import { CheckCircle2, XCircle, Loader2, Clock, AlertTriangle } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function fmtAmount(n) {
  return Number(n).toLocaleString("en-KE");
}

export default function Checkout() {
  const publicId = window.location.pathname.split("/pay/")[1];
  const [link, setLink] = useState(null);
  const [phone, setPhone] = useState("");
  const [stage, setStage] = useState("loading"); // loading | active | submitting | pending | success | failed | expired | paid | disabled | error
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState("");
  const pollRef = useRef(null);

  useEffect(() => {
    if (!publicId) { setStage("error"); setError("Invalid payment link."); return; }
    fetchLink();
    return () => stopPoll();
  }, [publicId]);

  const fetchLink = async () => {
    try {
      const res = await fetch(`${API_BASE}/pay/${publicId}`);
      if (res.status === 404) { setStage("error"); setError("Payment link not found."); return; }
      if (res.status === 410) {
        const data = await res.json().catch(() => ({}));
        if (data.detail?.includes("expired")) { setStage("expired"); }
        else { setStage("disabled"); }
        return;
      }
      if (!res.ok) { setStage("error"); setError("Unable to load payment details."); return; }
      const data = await res.json();
      setLink(data);
      if (data.status === "PAID") { setStage("paid"); }
      else if (data.status === "ACTIVE") { setStage("active"); }
      else if (data.status === "EXPIRED") { setStage("expired"); }
      else if (data.status === "DISABLED") { setStage("disabled"); }
      else { setStage("active"); }
    } catch {
      setStage("error"); setError("Unable to connect to payment service.");
    }
  };

  const stopPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const startPolling = () => {
    stopPoll();
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/pay/${publicId}/status`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "SUCCESS") {
          stopPoll();
          setReceipt(data.receipt || "");
          setStage("success");
        } else if (data.status === "FAILED" || data.status === "TIMEOUT") {
          stopPoll();
          setStage("failed");
        }
      } catch { /* keep polling */ }
    }, 3000);
    // Safety timeout: stop after 90 seconds
    setTimeout(() => {
      stopPoll();
      setStage(s => s === "pending" ? "failed" : s);
    }, 90000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!/^2547\d{8}$|^2541\d{8}$/.test(phone)) {
      setError("Enter a valid Safaricom number (07XXXXXXXX or 2547XXXXXXXX)");
      return;
    }
    setStage("submitting");
    try {
      const res = await fetch(`${API_BASE}/pay/${publicId}/stk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone }),
      });
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 409) { setStage("paid"); return; }
        if (res.status === 410) { setStage("expired"); return; }
        setError(data.detail || "Payment request failed.");
        setStage("active");
        return;
      }
      setStage("pending");
      startPolling();
    } catch {
      setError("Unable to connect to payment service.");
      setStage("active");
    }
  };

  const reset = () => {
    stopPoll();
    setPhone("");
    setError("");
    setReceipt("");
    if (link?.status === "ACTIVE") setStage("active");
  };

  // --- Render ---

  if (stage === "loading") {
    return (
      <div className="checkout-page">
        <div className="checkout-card">
          <div className="checkout-brand">PAYS</div>
          <div className="checkout-loading">
            <Loader2 className="spinner" size={24} />
            <span>Loading payment request...</span>
          </div>
        </div>
      </div>
    );
  }

  if (stage === "error") {
    return (
      <div className="checkout-page">
        <div className="checkout-card">
          <div className="checkout-brand">PAYS</div>
          <div className="checkout-status-icon error"><XCircle size={40} /></div>
          <div className="checkout-status-title">Payment unavailable</div>
          <div className="checkout-status-desc">{error}</div>
        </div>
      </div>
    );
  }

  if (stage === "expired") {
    return (
      <div className="checkout-page">
        <div className="checkout-card">
          <div className="checkout-brand">PAYS</div>
          <div className="checkout-status-icon warning"><Clock size={40} /></div>
          <div className="checkout-status-title">Payment link expired</div>
          <div className="checkout-status-desc">This payment request is no longer active.</div>
        </div>
      </div>
    );
  }

  if (stage === "disabled") {
    return (
      <div className="checkout-page">
        <div className="checkout-card">
          <div className="checkout-brand">PAYS</div>
          <div className="checkout-status-icon warning"><AlertTriangle size={40} /></div>
          <div className="checkout-status-title">Payment link unavailable</div>
          <div className="checkout-status-desc">This payment request is no longer active.</div>
        </div>
      </div>
    );
  }

  if (stage === "paid") {
    return (
      <div className="checkout-page">
        <div className="checkout-card">
          <div className="checkout-brand">PAYS</div>
          <div className="checkout-status-icon success"><CheckCircle2 size={40} /></div>
          <div className="checkout-status-title">Payment already completed</div>
          <div className="checkout-status-desc">This payment request has already been paid.</div>
        </div>
      </div>
    );
  }

  if (stage === "success") {
    return (
      <div className="checkout-page">
        <div className="checkout-card">
          <div className="checkout-brand">PAYS</div>
          <div className="checkout-status-icon success"><CheckCircle2 size={40} /></div>
          <div className="checkout-status-title">Payment successful</div>
          <div className="checkout-amount">KSh {fmtAmount(link.amount)}</div>
          {receipt && (
            <div className="checkout-receipt">
              <span className="receipt-label">M-Pesa Receipt</span>
              <span className="receipt-value">{receipt}</span>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (stage === "failed") {
    return (
      <div className="checkout-page">
        <div className="checkout-card">
          <div className="checkout-brand">PAYS</div>
          <div className="checkout-status-icon error"><XCircle size={40} /></div>
          <div className="checkout-status-title">Payment failed</div>
          <div className="checkout-status-desc">The M-Pesa payment was not completed.</div>
          <button className="btn-checkout" onClick={reset}>Try Again</button>
        </div>
      </div>
    );
  }

  if (stage === "pending") {
    return (
      <div className="checkout-page">
        <div className="checkout-card">
          <div className="checkout-brand">PAYS</div>
          <div className="checkout-status-icon pending"><Loader2 className="spinner" size={40} /></div>
          <div className="checkout-status-title">Check your phone</div>
          <div className="checkout-status-desc">
            An M-Pesa payment request has been sent to your phone.<br />
            Enter your M-Pesa PIN to complete the payment.
          </div>
          <div className="checkout-amount">KSh {fmtAmount(link.amount)}</div>
        </div>
      </div>
    );
  }

  // stage === "active"
  return (
    <div className="checkout-page">
      <div className="checkout-card">
        <div className="checkout-brand">PAYS</div>

        {link.description && (
          <div className="checkout-description">{link.description}</div>
        )}

        <div className="checkout-amount">KSh {fmtAmount(link.amount)}</div>

        <form onSubmit={handleSubmit} className="checkout-form">
          <label className="checkout-label">M-Pesa phone number</label>
          <input
            type="tel"
            className="checkout-input"
            placeholder="07XXXXXXXX"
            value={phone}
            onChange={(e) => setPhone(e.target.value.replace(/[^\d]/g, "").slice(0, 12))}
            autoFocus
            disabled={stage === "submitting"}
          />

          {error && <div className="checkout-error">{error}</div>}

          <button
            type="submit"
            className="btn-checkout"
            disabled={stage === "submitting" || !phone}
          >
            {stage === "submitting" ? (
              <><Loader2 className="spinner" size={16} /> Sending M-Pesa request...</>
            ) : (
              "Pay with M-Pesa"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
