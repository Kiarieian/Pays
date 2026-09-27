import React from "react";
import {
  LayoutDashboard,
  CreditCard,
  QrCode,
  Activity,
  Link2,
  Code,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

const NAV = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "payments", label: "Payments", icon: CreditCard },
  { key: "qr-payment", label: "QR Payment", icon: QrCode },
  { key: "payment-links", label: "Payment Links", icon: Link2 },
  { key: "transactions", label: "Transactions", icon: Activity },
  { key: "api-integration", label: "API", icon: Code },
];

export default function Sidebar({ active, onNavigate, collapsed, onToggleCollapse, mobileOpen, onMobileClose }) {
  return (
    <>
      {mobileOpen && <div className="sidebar-overlay" onClick={onMobileClose} />}
      <aside
        className={`sidebar ${collapsed ? "sidebar-collapsed" : "sidebar-expanded"} ${mobileOpen ? "sidebar-mobile-open" : ""}`}
      >
        <div className="sidebar-brand">
          <div className="sidebar-brand-content">
            <div className="sidebar-logo">KP</div>
            <span className="sidebar-brand-name">Kiarie Pay</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="sidebar-nav-section">
            <span className="sidebar-nav-label">Main</span>
            {NAV.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.key}
                  onClick={() => { onNavigate(item.key); onMobileClose(); }}
                  className={`nav-item ${active === item.key ? "active" : ""}`}
                >
                  <span className="nav-item-icon"><Icon size={18} /></span>
                  <span className="nav-item-label">{item.label}</span>
                </button>
              );
            })}
          </div>
        </nav>

        <div className="sidebar-footer">
          <div className="environment-indicator">
            <span className="environment-dot" />
            <div className="environment-content">
              <div className="environment-name">Sandbox</div>
              <div className="environment-description">Testing environment</div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
