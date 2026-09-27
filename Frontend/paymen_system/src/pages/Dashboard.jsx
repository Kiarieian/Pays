import React, { useMemo } from "react";
import { ArrowUpRight, CreditCard, QrCode } from "lucide-react";
import StatusBadge from "../components/StatusBadge";

function getTodayKey() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function isToday(dateStr) {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}` === getTodayKey();
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function fmtDate(s) {
  if (!s) return "";
  const d = new Date(s);
  return d.toLocaleDateString("en-KE", { day: "numeric", month: "short" });
}

function fmtTime(s) {
  if (!s) return "";
  const d = new Date(s);
  return d.toLocaleTimeString("en-KE", { hour: "2-digit", minute: "2-digit" });
}

export default function Dashboard({ payments, merchant, onNavigate }) {
  const todayPayments = useMemo(() => payments.filter((p) => isToday(p.created_at)), [payments]);
  const todaySuccess = useMemo(() => todayPayments.filter((p) => p.status === "SUCCESS"), [todayPayments]);
  const todayPending = useMemo(() => todayPayments.filter((p) => p.status === "PENDING"), [todayPayments]);
  const todayFailed = useMemo(() => todayPayments.filter((p) => p.status === "FAILED"), [todayPayments]);
  const totalCollected = useMemo(
    () => todaySuccess.reduce((s, p) => s + (Number(p.amount) || 0), 0),
    [todaySuccess]
  );
  const totalAllTime = useMemo(
    () => payments.filter((p) => p.status === "SUCCESS").reduce((s, p) => s + (Number(p.amount) || 0), 0),
    [payments]
  );

  const recent = useMemo(
    () => [...payments].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 6),
    [payments]
  );

  return (
    <div>
      <div className="page-header">
        <div className="page-header-content">
          <h1 className="page-title">
            {greeting()}, {merchant?.business_name?.split(" ")[0] || "there"}
          </h1>
          <p className="page-description">
            Your payment activity at a glance.
          </p>
        </div>
      </div>

      <div className="card card-padded" style={{ marginBottom: "var(--space-8)" }}>
        <p style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: "var(--font-semibold)" }}>
          Today's collections
        </p>
        <div className="flex items-end" style={{ gap: "var(--space-4)" }}>
          <span className="mono" style={{ fontSize: "var(--text-2xl)", fontWeight: "var(--font-semibold)", letterSpacing: "-0.03em", lineHeight: 1 }}>
            KSh {totalCollected.toLocaleString()}
          </span>
          {todaySuccess.length > 0 && (
            <span className="flex items-center text-success" style={{ gap: "var(--space-1)", fontSize: "var(--text-sm)", fontWeight: "var(--font-medium)", paddingBottom: "4px" }}>
              <ArrowUpRight size={14} />
              {todaySuccess.length} payment{todaySuccess.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>

        <div className="grid grid-4 gap-4" style={{ marginTop: "var(--space-6)", borderTop: "1px solid var(--border-subtle)", paddingTop: "var(--space-5)" }}>
          <div>
            <p className="text-muted" style={{ fontSize: "var(--text-xs)", marginBottom: "var(--space-1)" }}>Successful</p>
            <p className="mono text-success" style={{ fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)" }}>{todaySuccess.length}</p>
          </div>
          <div>
            <p className="text-muted" style={{ fontSize: "var(--text-xs)", marginBottom: "var(--space-1)" }}>Pending</p>
            <p className="mono text-warning" style={{ fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)" }}>{todayPending.length}</p>
          </div>
          <div>
            <p className="text-muted" style={{ fontSize: "var(--text-xs)", marginBottom: "var(--space-1)" }}>Failed</p>
            <p className="mono text-error" style={{ fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)" }}>{todayFailed.length}</p>
          </div>
          <div className="text-right">
            <p className="text-muted" style={{ fontSize: "var(--text-xs)", marginBottom: "var(--space-1)" }}>All-time total</p>
            <p className="mono" style={{ fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)" }}>
              KSh {totalAllTime.toLocaleString()}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-2 gap-6">
        <div>
          <div className="flex items-center justify-between" style={{ marginBottom: "var(--space-4)" }}>
            <h2 style={{ fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)" }}>Recent activity</h2>
            {payments.length > 6 && (
              <button
                className="text-success font-medium"
                style={{ fontSize: "var(--text-sm)", cursor: "pointer", background: "none", border: "none" }}
                onClick={() => onNavigate("transactions")}
              >
                View all
              </button>
            )}
          </div>

          {recent.length === 0 ? (
            <div className="card">
              <div className="empty-state" style={{ minHeight: "200px" }}>
                <p className="text-muted" style={{ fontSize: "var(--text-sm)" }}>No transactions yet</p>
              </div>
            </div>
          ) : (
            <div className="card">
              {recent.map((p, i) => (
                <div
                  key={p.id}
                  className="flex items-center justify-between"
                  style={{ padding: "var(--space-3) var(--space-5)", borderBottom: i < recent.length - 1 ? "1px solid var(--border-subtle)" : "none" }}
                >
                  <div className="flex items-center min-w-0" style={{ gap: "var(--space-4)" }}>
                    <div className="min-w-0">
                      <p className="truncate mono" style={{ fontSize: "var(--text-sm)" }}>
                        {p.phone}
                      </p>
                      <p className="text-muted" style={{ fontSize: "var(--text-xs)" }}>
                        {fmtDate(p.created_at)} {fmtTime(p.created_at)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center" style={{ gap: "var(--space-4)" }}>
                    <span className="mono font-medium" style={{ fontSize: "var(--text-sm)" }}>
                      KSh {(Number(p.amount) || 0).toLocaleString()}
                    </span>
                    <StatusBadge status={p.status} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <h2 style={{ fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-4)" }}>Quick actions</h2>
          <div className="flex flex-col" style={{ gap: "var(--space-3)" }}>
            <button
              className="card flex items-center"
              style={{ padding: "var(--space-4)", cursor: "pointer", textAlign: "left", gap: "var(--space-3)" }}
              onClick={() => onNavigate("payments")}
            >
              <div className="flex items-center justify-center" style={{ width: "40px", height: "40px", background: "var(--green-bg)", borderRadius: "var(--radius-md)" }}>
                <CreditCard size={18} className="text-success" />
              </div>
              <div>
                <p className="font-medium" style={{ fontSize: "var(--text-sm)" }}>STK Payment</p>
                <p className="text-muted" style={{ fontSize: "var(--text-xs)" }}>Collect via push</p>
              </div>
            </button>
            <button
              className="card flex items-center"
              style={{ padding: "var(--space-4)", cursor: "pointer", textAlign: "left", gap: "var(--space-3)" }}
              onClick={() => onNavigate("qr-payment")}
            >
              <div className="flex items-center justify-center" style={{ width: "40px", height: "40px", background: "var(--green-bg)", borderRadius: "var(--radius-md)" }}>
                <QrCode size={18} className="text-success" />
              </div>
              <div>
                <p className="font-medium" style={{ fontSize: "var(--text-sm)" }}>QR Payment</p>
                <p className="text-muted" style={{ fontSize: "var(--text-xs)" }}>Generate scan code</p>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
