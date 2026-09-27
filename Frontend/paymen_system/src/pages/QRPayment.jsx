import React, { useState } from "react";
import { Loader2, QrCode } from "lucide-react";
import api, { ApiError } from "../Api/api";

export default function QRPayment() {
  const [qrAmount, setQrAmount] = useState("");
  const [qrRef, setQrRef] = useState("");
  const [qrCode, setQrCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleGenerate = async (e) => {
    e.preventDefault();
    setError("");
    if (!(Number(qrAmount) > 0)) { setError("Enter an amount greater than 0"); return; }
    setLoading(true);
    setQrCode("");
    try {
      const data = await api.generateQr({ amount: Number(qrAmount), account_reference: qrRef || undefined });
      setQrRef(data.account_reference || "");
      if (data.qr_code_base64) {
        setQrCode(data.qr_code_base64);
      } else {
        throw new Error("Server did not return a QR image");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate QR code.");
    } finally {
      setLoading(false);
    }
  };

  const reset = () => { setQrCode(""); setQrAmount(""); setQrRef(""); setError(""); };

  return (
    <div>
      <div className="page-header">
        <div className="page-header-content">
          <h1 className="page-title">QR Payment</h1>
          <p className="page-description">
            Generate a dynamic M-Pesa QR code for customers to scan and pay.
          </p>
        </div>
      </div>

      <div className="payment-layout">
        <div className="payment-form">
          <form onSubmit={handleGenerate}>
            <div className="payment-form-section">
              <div className="payment-fields">
                <div className="form-field payment-fields-full">
                  <label className="form-label">Amount</label>
                  <div className="amount-input-wrapper">
                    <span className="amount-prefix">KSh</span>
                    <input
                      type="number"
                      min="1"
                      className="input amount-input"
                      placeholder="0"
                      value={qrAmount}
                      disabled={loading}
                      onChange={(e) => setQrAmount(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-field payment-fields-full">
                  <label className="form-label">
                    Reference <span className="form-label-optional">(optional)</span>
                  </label>
                  <input
                    type="text"
                    className="input"
                    placeholder="e.g. Order #123"
                    value={qrRef}
                    disabled={loading}
                    onChange={(e) => setQrRef(e.target.value)}
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
                disabled={loading}
                className="btn btn-primary flex-1"
              >
                {loading ? (
                  <><Loader2 size={15} className="spinner" /> Generating...</>
                ) : (
                  <><QrCode size={15} /> Generate QR Code</>
                )}
              </button>
              {qrCode && (
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
            <div
              className="flex items-center justify-center overflow-hidden"
              style={{
                width: "100%",
                maxWidth: "220px",
                height: "220px",
                margin: "0 auto var(--space-5)",
                borderRadius: "var(--radius-lg)",
                background: "#fff",
                border: "1px solid var(--border-subtle)",
              }}
            >
              {loading && <Loader2 className="spinner" size={28} style={{ color: "var(--green)" }} />}

              {!loading && !qrCode && (
                <div className="text-center" style={{ padding: "var(--space-6)" }}>
                  <QrCode size={36} className="text-muted mx-auto" style={{ marginBottom: "var(--space-2)" }} />
                  <p className="text-muted" style={{ fontSize: "var(--text-xs)" }}>Your QR code will appear here</p>
                </div>
              )}

              {!loading && qrCode && (
                <img
                  src={`data:image/png;base64,${qrCode}`}
                  alt="M-Pesa QR code"
                  style={{ width: "100%", height: "100%", objectFit: "contain" }}
                />
              )}
            </div>

            <p className="mono font-semibold text-center" style={{ fontSize: "var(--text-xl)" }}>
              {qrAmount ? `KSh ${Number(qrAmount).toLocaleString()}` : "—"}
            </p>
            {qrRef && (
              <p className="mono text-muted text-center" style={{ fontSize: "var(--text-xs)", marginTop: "var(--space-1)" }}>
                {qrRef}
              </p>
            )}
            <p className="text-muted text-center" style={{ fontSize: "var(--text-sm)", marginTop: "var(--space-3)" }}>
              Customer opens M-Pesa → Scan QR to pay
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
