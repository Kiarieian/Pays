import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Smartphone,
  CheckCircle2,
  XCircle,
  Loader2,
  ArrowRight,
  Receipt,
  Clock,
  Wifi,
  Battery,
  Signal,
} from "lucide-react";
import api, { ApiError } from "../Api/api";
import "../components/styles/Payment.css";

/* ------------------------------------------------------------------
   KIARIE PAY — STK Push Dashboard
   Design language: a warm, human till-receipt — not a cold terminal.
   The signature element is a thermal-printer ticket that "prints"
   the real STK prompt line by line, and stamps PAID / FAILED in ink
   when the customer responds.
------------------------------------------------------------------- */

function classNames(...c) {
  return c.filter(Boolean).join(" ");
}

/* ---------------------------- Receipt Screen ---------------------------- */

function TillScreen({ stage, phone, amount, receipt }) {
  // stage: idle | dialing | prompt | typing-pin | confirming | success | failed
  const promptText = `M-PESA\nConfirm to pay\nKSh ${amount || "0"}\nto KIARIE STR\n\nEnter PIN:`;
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (stage !== "prompt") {
      setTyped("");
      return;
    }
    let i = 0;
    const t = setInterval(() => {
      i++;
      setTyped(promptText.slice(0, i));
      if (i >= promptText.length) clearInterval(t);
    }, 18);
    return () => clearInterval(t);
  }, [stage]); // eslint-disable-line

  return (
    <div className="pd-till">
      <div className="pd-till__screen">
        <div className="pd-till__notch" />
        <div className="pd-till__status">
          <span>9:41</span>
          <div style={{ display: "flex", gap: 4 }}>
            <Signal size={10} />
            <Wifi size={10} />
            <Battery size={11} />
          </div>
        </div>

        <div className="pd-till__body">
          {stage === "idle" && (
            <div className="pd-idle">
              <div className="pd-idle__icon">
                <Smartphone size={22} color="var(--forest)" />
              </div>
              <p className="pd-idle__text">Waiting to send request…</p>
            </div>
          )}

          {stage === "dialing" && (
            <div className="pd-dialing">
              <Loader2 className="pd-spin" size={26} color="var(--forest)" />
              <p className="pd-dialing__text">
                Sending push to
                <br />
                <span className="pd-dialing__number">{phone || "—"}</span>
              </p>
              <div className="pd-dots">
                <span />
                <span />
                <span />
              </div>
            </div>
          )}

          {(stage === "prompt" || stage === "typing-pin" || stage === "confirming") && (
            <div className="pd-ticket">
              {typed}
              <span className="pd-ticket__cursor" />
              {stage === "typing-pin" && (
                <div className="pd-dots" style={{ marginTop: 10 }}>
                  <span />
                  <span />
                  <span />
                </div>
              )}
              {stage === "confirming" && (
                <p className="pd-ticket__note">Confirming with Safaricom…</p>
              )}
            </div>
          )}

          {stage === "success" && (
            <div className="pd-stamp pd-stamp--paid">
              <div className="pd-stamp__ring">
                <CheckCircle2 size={28} />
              </div>
              <p className="pd-stamp__title">Payment received</p>
              <p className="pd-stamp__sub">{receipt || "—"}</p>
            </div>
          )}

          {stage === "failed" && (
            <div className="pd-stamp pd-stamp--failed">
              <div className="pd-stamp__ring">
                <XCircle size={28} />
              </div>
              <p className="pd-stamp__title">Payment failed</p>
              <p className="pd-stamp__sub">Customer cancelled or timed out</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------ QR Ticket -------------------------------- */

function QrScreen({ loading, qrCode, amount, qrRef }) {
  return (
    <div className="pd-qr-card">
      <div className="pd-qr-window">
        {loading && <Loader2 className="pd-spin" size={26} color="var(--forest-deep)" />}

        {!loading && !qrCode && (
          <p className="pd-qr-placeholder">Enter an amount to generate a code</p>
        )}

        {!loading && qrCode && (
          <>
            <img src={`data:image/png;base64,${qrCode}`} alt="M-Pesa QR code" />
            <div className="pd-qr-scan" />
          </>
        )}
      </div>

      <p className="pd-qr-amount">{amount ? `KSh ${amount}` : "—"}</p>
      {qrRef && <p className="pd-qr-ref">ref: {qrRef}</p>}
      <p className="pd-qr-caption">
        Customer opens M-Pesa → Scan QR
        <br />
        to pay this amount instantly.
      </p>
    </div>
  );
}

/* ------------------------------ Status Pill ------------------------------ */

function StatusPill({ status }) {
  const map = {
    SUCCESS: { cls: "pd-pill--success", label: "Success", icon: CheckCircle2 },
    Pending: { cls: "pd-pill--pending", label: "Pending", icon: Clock },
    FAILED: { cls: "pd-pill--failed", label: "Failed", icon: XCircle },
  };
  const s = map[status] || map.Pending;
  const Icon = s.icon;
  return (
    <span className={classNames("pd-pill", s.cls)}>
      <Icon size={12} />
      {s.label}
    </span>
  );
}

/* -------------------------------- App ----------------------------------- */

export default function PaymentDashboard() {
  const [mode, setMode] = useState("stk"); // "stk" | "qr"
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [stage, setStage] = useState("idle");
  const [error, setError] = useState("");
  const [activeReceipt, setActiveReceipt] = useState("");
  const [payments, setPayments] = useState([]);
  const [loadingList, setLoadingList] = useState(false);
  const pollRef = useRef(null);

  // Scan-to-pay state
  const [qrAmount, setQrAmount] = useState("");
  const [qrCode, setQrCode] = useState(""); // base64 png string
  const [qrLoading, setQrLoading] = useState(false);
  const [qrError, setQrError] = useState("");
  const [qrRef, setQrRef] = useState("");

  const validPhone = /^2547\d{8}$|^2541\d{8}$/.test(phone);
  const validAmount = Number(amount) > 0;

  const fetchPayments = useCallback(async () => {
    setLoadingList(true);
    try {
      const data = await api.listPayments();
      setPayments(Array.isArray(data) ? data : []);
    } catch (e) {
      // Backend may not be running in this preview — fail quietly.
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    fetchPayments();
  }, [fetchPayments]);

  const stopPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => () => stopPoll(), []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!validPhone) {
      setError("Enter a valid Safaricom number, e.g. 2547XXXXXXXX");
      return;
    }
    if (!validAmount) {
      setError("Enter an amount greater than 0");
      return;
    }

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
          if (match && match.status !== "Pending") {
            stopPoll();
            if (match.status === "SUCCESS") {
              setActiveReceipt(match.mpesa_receipt || "");
              setStage("success");
            } else {
              setStage("failed");
            }
            fetchPayments();
          }
        } catch {
          /* keep polling */
        }
      }, 2500);

      setTimeout(() => {
        stopPoll();
        setStage((s) => (s === "confirming" || s === "prompt" || s === "typing-pin" ? "failed" : s));
      }, 45000);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not reach the payment service. Check your connection and try again."
      );
      setStage("idle");
    }
  };

  const resetFlow = () => {
    stopPoll();
    setStage("idle");
    setActiveReceipt("");
    setPhone("");
    setAmount("");
    fetchPayments();
  };

  const handleGenerateQr = async (e) => {
    e.preventDefault();
    setQrError("");
    if (!(Number(qrAmount) > 0)) {
      setQrError("Enter an amount greater than 0");
      return;
    }
    setQrLoading(true);
    setQrCode("");
    try {
      const data = await api.generateQr({ amount: Number(qrAmount) });
      setQrRef(data.account_ref || "");
      if (data.qr_code) {
        setQrCode(data.qr_code);
      } else {
        throw new Error("Server did not return a QR image");
      }
    } catch (err) {
      setQrError(err.message || "Something went wrong generating the QR code.");
    } finally {
      setQrLoading(false);
    }
  };

  const resetQr = () => {
    setQrCode("");
    setQrAmount("");
    setQrError("");
    setQrRef("");
  };

  const busy = ["dialing", "prompt", "typing-pin", "confirming"].includes(stage);

  return (
    <div className="pd-root">
      <div className="pd-grain" />
      <div className="pd-blob pd-blob--mango" />
      <div className="pd-blob pd-blob--forest" />

      <header className="pd-header">
        <div className="pd-brand">
          <div className="pd-brand__mark">KP</div>
          <div>
            <p className="pd-brand__name">Kiarie Pay</p>
            <p className="pd-brand__tag">Lipa na M-Pesa, instantly</p>
          </div>
        </div>
        <div className="pd-header__badge">
          <span className="pd-header__dot" />
          sandbox · daraja
        </div>
      </header>

      <main className="pd-main">
        <div>
          <p className="pd-eyebrow">Request a payment</p>
          <h1 className="pd-title">
            Get paid in <em>one tap.</em>
          </h1>
          <p className="pd-subtitle">
            Send an STK push straight to the customer's phone, or hand them a
            QR code to scan — watch the till print the request live, right
            beside this form.
          </p>

          <div className="pd-tabs">
            {[
              { key: "stk", label: "STK Push" },
              { key: "qr", label: "Scan to Pay" },
            ].map((t) => (
              <button
                key={t.key}
                onClick={() => setMode(t.key)}
                className={classNames("pd-tab", mode === t.key && "pd-tab--active")}
              >
                {t.label}
              </button>
            ))}
          </div>

          {mode === "stk" ? (
            <form onSubmit={handleSubmit} className="pd-card">
              <div className="pd-field">
                <label className="pd-label">Customer phone number</label>
                <input
                  type="tel"
                  placeholder="2547XXXXXXXX"
                  value={phone}
                  disabled={busy}
                  onChange={(e) => setPhone(e.target.value.replace(/[^\d]/g, ""))}
                  className="pd-input"
                />
              </div>

              <div className="pd-field">
                <label className="pd-label">Amount (KSh)</label>
                <input
                  type="number"
                  min="1"
                  placeholder="0"
                  value={amount}
                  disabled={busy}
                  onChange={(e) => setAmount(e.target.value)}
                  className="pd-input"
                />
              </div>

              {error && <p className="pd-error">{error}</p>}

              <button type="submit" disabled={busy} className="pd-btn">
                {busy ? (
                  <>
                    <Loader2 size={16} className="pd-spin" /> Sending push…
                  </>
                ) : (
                  <>
                    Send STK push <ArrowRight size={16} />
                  </>
                )}
              </button>

              {(stage === "success" || stage === "failed") && (
                <button type="button" onClick={resetFlow} className="pd-btn-ghost">
                  New payment request
                </button>
              )}
            </form>
          ) : (
            <form onSubmit={handleGenerateQr} className="pd-card">
              <div className="pd-field">
                <label className="pd-label">Amount (KSh)</label>
                <input
                  type="number"
                  min="1"
                  placeholder="0"
                  value={qrAmount}
                  disabled={qrLoading}
                  onChange={(e) => setQrAmount(e.target.value)}
                  className="pd-input"
                />
              </div>

              {qrError && <p className="pd-error">{qrError}</p>}

              <button type="submit" disabled={qrLoading} className="pd-btn">
                {qrLoading ? (
                  <>
                    <Loader2 size={16} className="pd-spin" /> Generating code…
                  </>
                ) : (
                  <>
                    Generate QR code <ArrowRight size={16} />
                  </>
                )}
              </button>

              {qrCode && (
                <button type="button" onClick={resetQr} className="pd-btn-ghost">
                  New QR code
                </button>
              )}
            </form>
          )}

          {mode === "stk" && (
            <div className="pd-history">
              <div className="pd-history__head">
                <h2 className="pd-history__title">
                  <Receipt size={15} /> Recent transactions
                </h2>
                {loadingList && <Loader2 size={14} className="pd-spin" color="var(--ink-faint)" />}
              </div>

              <div className="pd-table-wrap">
                {payments.length === 0 ? (
                  <div className="pd-empty">
                    No transactions yet — they'll appear here once a payment is sent.
                  </div>
                ) : (
                  <table className="pd-table">
                    <thead>
                      <tr>
                        <th>Phone</th>
                        <th>Amount</th>
                        <th>Status</th>
                        <th>Receipt</th>
                      </tr>
                    </thead>
                    <tbody>
                      {payments.slice(0, 8).map((p) => (
                        <tr key={p.id}>
                          <td>{p.phone}</td>
                          <td>KSh {p.amount}</td>
                          <td>
                            <StatusPill status={p.status} />
                          </td>
                          <td>{p.mpesa_receipt || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="pd-preview">
          <p className="pd-preview__label">
            {mode === "stk" ? "Live customer screen" : "Customer scans this"}
          </p>
          {mode === "stk" ? (
            <TillScreen stage={stage} phone={phone} amount={amount} receipt={activeReceipt} />
          ) : (
            <QrScreen loading={qrLoading} qrCode={qrCode} amount={qrAmount} qrRef={qrRef} />
          )}
        </div>
      </main>
    </div>
  );
}