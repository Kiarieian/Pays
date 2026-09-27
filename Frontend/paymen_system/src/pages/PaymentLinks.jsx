import React, { useState, useEffect } from "react";
import {
  Link2,
  Plus,
  Copy,
  Check,
  Ban,
  Loader2,
  ExternalLink,
  Clock,
} from "lucide-react";
import api, { ApiError } from "../Api/api";
import StatusBadge from "../components/StatusBadge";

function CopyBtn({ text }) {
  const [ok, setOk] = useState(false);
  return (
    <button
      className="btn btn-ghost"
      style={{ minHeight: "28px", padding: "0 var(--space-2)" }}
      onClick={() => {
        navigator.clipboard.writeText(text);
        setOk(true);
        setTimeout(() => setOk(false), 1500);
      }}
    >
      {ok ? <Check size={13} className="text-success" /> : <Copy size={13} />}
    </button>
  );
}

function fmtDate(s) {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleDateString("en-KE", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function PaymentLinks() {
  const [links, setLinks] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Create form state
  const [showCreate, setShowCreate] = useState(false);
  const [createAmount, setCreateAmount] = useState("");
  const [createDesc, setCreateDesc] = useState("");
  const [createRef, setCreateRef] = useState("");
  const [createExpiry, setCreateExpiry] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createdLink, setCreatedLink] = useState(null);

  // Disable state
  const [disabling, setDisabling] = useState(null);

  const fetchLinks = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.listPaymentLinks();
      setLinks(data.links || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load payment links.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLinks();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreateError("");
    if (!(Number(createAmount) > 0)) {
      setCreateError("Enter an amount greater than 0.");
      return;
    }
    setCreating(true);
    try {
      const data = await api.createPaymentLink({
        amount: Number(createAmount),
        description: createDesc || undefined,
        account_reference: createRef || undefined,
        expires_at: createExpiry ? new Date(createExpiry).toISOString() : undefined,
      });
      setCreatedLink(data);
      setCreateAmount("");
      setCreateDesc("");
      setCreateRef("");
      setCreateExpiry("");
      setShowCreate(false);
      fetchLinks();
    } catch (err) {
      setCreateError(
        err instanceof ApiError ? err.message : "Failed to create payment link."
      );
    } finally {
      setCreating(false);
    }
  };

  const handleDisable = async (publicId) => {
    setDisabling(publicId);
    try {
      const result = await api.disablePaymentLink(publicId);
      setLinks((prev) =>
        prev.map((l) =>
          l.public_id === publicId ? { ...l, status: result.status } : l
        )
      );
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to disable link."
      );
    } finally {
      setDisabling(null);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-header-content">
          <h1 className="page-title">Payment Links</h1>
          <p className="page-description">
            Create shareable payment links for your customers.
          </p>
        </div>
        <div className="page-actions">
          <button
            className="btn btn-primary"
            onClick={() => {
              setShowCreate(!showCreate);
              setCreatedLink(null);
              setCreateError("");
            }}
          >
            <Plus size={15} /> New Link
          </button>
        </div>
      </div>

      {/* Created link success */}
      {createdLink && (
        <div className="card card-padded" style={{ marginBottom: "var(--space-6)" }}>
          <div className="flex items-start" style={{ gap: "var(--space-3)" }}>
            <div className="flex items-center justify-center" style={{ width: "32px", height: "32px", background: "var(--green-bg)", borderRadius: "var(--radius-md)", flexShrink: 0 }}>
              <Check size={16} className="text-success" />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p className="font-semibold" style={{ fontSize: "var(--text-sm)", marginBottom: "var(--space-1)" }}>
                Payment link created
              </p>
              <p className="text-muted" style={{ fontSize: "var(--text-xs)", marginBottom: "var(--space-3)" }}>
                Share this link with your customer to collect payment.
              </p>
              <div className="api-key-display">
                <span className="api-key-value">{createdLink.payment_url}</span>
                <CopyBtn text={createdLink.payment_url} />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="card" style={{ marginBottom: "var(--space-6)" }}>
          <div className="card-header">
            <div className="card-header-content">
              <div className="card-title">Create payment link</div>
              <div className="card-description">
                Your customer will see this amount when they open the link.
              </div>
            </div>
          </div>
          <div className="card-body">
            <form onSubmit={handleCreate} className="payment-form">
              <div className="payment-fields">
                <div className="form-field">
                  <label className="form-label">Amount (KES)</label>
                  <div className="amount-input-wrapper">
                    <span className="amount-prefix">KSh</span>
                    <input
                      type="number"
                      min="1"
                      className="input amount-input"
                      placeholder="0"
                      value={createAmount}
                      disabled={creating}
                      onChange={(e) => setCreateAmount(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-field">
                  <label className="form-label">
                    Description <span className="form-label-optional">(optional)</span>
                  </label>
                  <input
                    type="text"
                    className="input"
                    placeholder="e.g. Photography deposit"
                    value={createDesc}
                    disabled={creating}
                    onChange={(e) => setCreateDesc(e.target.value)}
                  />
                </div>

                <div className="form-field">
                  <label className="form-label">
                    Account reference <span className="form-label-optional">(optional)</span>
                  </label>
                  <input
                    type="text"
                    className="input"
                    placeholder="e.g. ORDER-001"
                    value={createRef}
                    disabled={creating}
                    onChange={(e) => setCreateRef(e.target.value)}
                  />
                </div>

                <div className="form-field">
                  <label className="form-label">
                    Expires <span className="form-label-optional">(optional)</span>
                  </label>
                  <input
                    type="datetime-local"
                    className="input"
                    value={createExpiry}
                    disabled={creating}
                    onChange={(e) => setCreateExpiry(e.target.value)}
                  />
                </div>
              </div>

              {createError && (
                <div className="alert alert-error">
                  <div className="alert-content">
                    <div className="alert-message">{createError}</div>
                  </div>
                </div>
              )}

              <div className="flex" style={{ gap: "var(--space-3)" }}>
                <button
                  type="submit"
                  disabled={creating}
                  className="btn btn-primary"
                >
                  {creating ? (
                    <><Loader2 size={15} className="spinner" /> Creating...</>
                  ) : (
                    <><Link2 size={15} /> Create Link</>
                  )}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowCreate(false)}
                  disabled={creating}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Links list */}
      {loading ? (
        <div className="table-container">
          <div className="empty-state">
            <div className="flex items-center" style={{ gap: "var(--space-2)", color: "var(--text-muted)" }}>
              <Loader2 className="spinner" size={16} />
              <span style={{ fontSize: "var(--text-sm)" }}>Loading payment links...</span>
            </div>
          </div>
        </div>
      ) : error ? (
        <div className="card card-padded">
          <div className="alert alert-error">
            <div className="alert-content">
              <div className="alert-message">{error}</div>
            </div>
          </div>
          <button
            className="btn btn-secondary"
            style={{ marginTop: "var(--space-4)" }}
            onClick={fetchLinks}
          >
            Retry
          </button>
        </div>
      ) : links.length === 0 ? (
        <div className="table-container">
          <div className="empty-state">
            <div className="empty-state-icon">
              <Link2 size={20} />
            </div>
            <div className="empty-state-title">No payment links</div>
            <div className="empty-state-description">
              Create your first payment link to start collecting payments.
            </div>
            <button
              className="btn btn-primary"
              style={{ marginTop: "var(--space-4)" }}
              onClick={() => setShowCreate(true)}
            >
              <Plus size={15} /> Create Link
            </button>
          </div>
        </div>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                {["Description", "Amount", "Status", "Created", "Link", "Action"].map(
                  (h) => (
                    <th key={h}>{h}</th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {links.map((link) => (
                <tr key={link.public_id}>
                  <td>
                    <div className="font-medium" style={{ fontSize: "var(--text-sm)" }}>
                      {link.description || "—"}
                    </div>
                    {link.account_reference && (
                      <div className="text-muted" style={{ fontSize: "var(--text-xs)" }}>
                        {link.account_reference}
                      </div>
                    )}
                  </td>
                  <td className="mono font-medium">
                    KSh {(Number(link.amount) || 0).toLocaleString()}
                  </td>
                  <td>
                    <StatusBadge
                      status={
                        link.status === "ACTIVE"
                          ? "PENDING"
                          : link.status === "PAID"
                          ? "SUCCESS"
                          : link.status === "DISABLED"
                          ? "FAILED"
                          : "PENDING"
                      }
                    />
                  </td>
                  <td>
                    <div style={{ fontSize: "var(--text-sm)" }}>{fmtDate(link.created_at)}</div>
                    {link.expires_at && (
                      <div className="text-muted flex items-center" style={{ fontSize: "var(--text-xs)", gap: "var(--space-1)" }}>
                        <Clock size={10} /> Expires {fmtDate(link.expires_at)}
                      </div>
                    )}
                  </td>
                  <td>
                    <div className="flex items-center" style={{ gap: "var(--space-1)" }}>
                      <span className="mono text-muted truncate" style={{ fontSize: "var(--text-xs)", maxWidth: "140px" }}>
                        {link.payment_url}
                      </span>
                      <CopyBtn text={link.payment_url} />
                    </div>
                  </td>
                  <td>
                    {link.status === "ACTIVE" && (
                      <button
                        className="btn btn-ghost"
                        style={{
                          minHeight: "28px",
                          padding: "0 var(--space-2)",
                          fontSize: "var(--text-xs)",
                          color: "var(--red)",
                        }}
                        disabled={disabling === link.public_id}
                        onClick={() => handleDisable(link.public_id)}
                      >
                        {disabling === link.public_id ? (
                          <Loader2 size={12} className="spinner" />
                        ) : (
                          <><Ban size={12} /> Disable</>
                        )}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {links.length > 0 && (
        <p
          className="text-right text-muted"
          style={{ fontSize: "var(--text-xs)", marginTop: "var(--space-3)" }}
        >
          {total} link{total !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
