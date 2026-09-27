import React, { useState, useMemo } from "react";
import { RefreshCw, Search } from "lucide-react";
import TransactionTable from "../components/TransactionTable";

export default function Transactions({ payments, loading, onRefresh }) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const filtered = useMemo(() => {
    let list = [...payments].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    if (statusFilter !== "all") list = list.filter((p) => p.status === statusFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (p) =>
          (p.phone && p.phone.includes(q)) ||
          (p.mpesa_receipt && p.mpesa_receipt.toLowerCase().includes(q)) ||
          String(p.id).includes(q)
      );
    }
    return list;
  }, [payments, search, statusFilter]);

  const filters = [
    { key: "all", label: "All" },
    { key: "SUCCESS", label: "Successful" },
    { key: "PENDING", label: "Pending" },
    { key: "FAILED", label: "Failed" },
  ];

  return (
    <div>
      <div className="page-header">
        <div className="page-header-content">
          <h1 className="page-title">Transactions</h1>
          <p className="page-description">
            Monitor every payment processed through your platform.
          </p>
        </div>
        <div className="page-actions">
          <button
            className="btn btn-secondary"
            onClick={onRefresh}
          >
            <RefreshCw size={14} className={loading ? "spinner" : ""} />
            Refresh
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center" style={{ gap: "var(--space-3)", marginBottom: "var(--space-5)" }}>
        <div className="relative" style={{ flex: "1 1 200px", maxWidth: "320px" }}>
          <Search size={15} className="text-muted" style={{ position: "absolute", left: "var(--space-3)", top: "50%", transform: "translateY(-50%)" }} />
          <input
            type="text"
            className="input"
            placeholder="Search phone, receipt, or ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ paddingLeft: "36px" }}
          />
        </div>

        <div className="flex" style={{ background: "var(--bg-raised)", borderRadius: "var(--radius-md)", padding: "3px", gap: "var(--space-1)" }}>
          {filters.map((f) => (
            <button
              key={f.key}
              onClick={() => setStatusFilter(f.key)}
              className="btn btn-ghost"
              style={{
                minHeight: "32px",
                padding: "0 var(--space-3)",
                fontSize: "var(--text-xs)",
                background: statusFilter === f.key ? "var(--bg-surface)" : "transparent",
                color: statusFilter === f.key ? "var(--text)" : "var(--text-muted)",
                border: statusFilter === f.key ? "1px solid var(--border)" : "1px solid transparent",
                boxShadow: statusFilter === f.key ? "var(--shadow-sm)" : "none",
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <TransactionTable payments={filtered} loading={loading} />

      <p className="text-right text-muted" style={{ fontSize: "var(--text-xs)", marginTop: "var(--space-3)" }}>
        {filtered.length} record{filtered.length !== 1 ? "s" : ""}
        {(search || statusFilter !== "all") && ` of ${payments.length}`}
      </p>
    </div>
  );
}
