import React from "react";
import StatusBadge from "./StatusBadge";

function fmtDate(s) {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" });
}

function fmtTime(s) {
  if (!s) return "";
  const d = new Date(s);
  return d.toLocaleTimeString("en-KE", { hour: "2-digit", minute: "2-digit" });
}

export default function TransactionTable({ payments, loading }) {
  if (loading && payments.length === 0) {
    return (
      <div className="table-container">
        <div className="empty-state">
          <p className="text-muted" style={{ fontSize: "var(--text-sm)" }}>Loading transactions...</p>
        </div>
      </div>
    );
  }

  if (payments.length === 0) {
    return (
      <div className="table-container">
        <div className="empty-state">
          <div className="empty-state-icon">
            <span style={{ fontSize: "var(--text-lg)" }}>—</span>
          </div>
          <div className="empty-state-title">No transactions yet</div>
          <div className="empty-state-description">
            Payment records will appear here once you process your first transaction.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="table-container">
      <table className="table">
        <thead>
          <tr>
            {["Date", "Customer", "Amount", "Status", "Receipt"].map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {payments.map((p) => (
            <tr key={p.id}>
              <td>
                <div>{fmtDate(p.created_at)}</div>
                <div className="text-muted" style={{ fontSize: "var(--text-xs)" }}>{fmtTime(p.created_at)}</div>
              </td>
              <td className="mono">{p.phone}</td>
              <td className="mono font-medium">
                KSh {(Number(p.amount) || 0).toLocaleString()}
              </td>
              <td><StatusBadge status={p.status} /></td>
              <td className="mono text-muted" style={{ fontSize: "var(--text-xs)" }}>
                {p.mpesa_receipt || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
