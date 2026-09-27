import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import AppHeader from "./components/AppHeader";
import Dashboard from "./pages/Dashboard";
import Payments from "./pages/Payments";
import QRPayment from "./pages/QRPayment";
import PaymentLinks from "./pages/PaymentLinks";
import Transactions from "./pages/Transactions";
import APIIntegration from "./pages/APIIntegration";
import Checkout from "./pages/Checkout";
import Login from "./pages/Login";
import api, { getSessionToken, clearSessionToken } from "./Api/api";

function getPublicIdFromPath() {
  const path = window.location.pathname;
  if (path.startsWith("/pay/")) {
    return path.slice("/pay/".length) || null;
  }
  return null;
}

export default function App() {
  const publicId = getPublicIdFromPath();

  // Public checkout route — no auth, no dashboard shell
  if (publicId) {
    return <Checkout key={publicId} />;
  }

  return <DashboardApp />;
}

function DashboardApp() {
  const [page, setPage] = useState("dashboard");
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [merchant, setMerchant] = useState(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const fetchPayments = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listPayments();
      setPayments(Array.isArray(data) ? data : []);
    } catch { /* backend may be offline */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (!getSessionToken()) {
      setReady(true);
      return;
    }
    api.getProfile()
      .then((m) => { setMerchant(m); setLoggedIn(true); return api.listPayments(); })
      .then((d) => { setPayments(Array.isArray(d) ? d : []); setReady(true); })
      .catch(() => {
        clearSessionToken();
        setReady(true);
      });
  }, []);

  const handleLogin = async (data) => {
    setLoggedIn(true);
    try {
      const m = await api.getProfile();
      setMerchant(m);
      const d = await api.listPayments();
      setPayments(Array.isArray(d) ? d : []);
    } catch { /* profile load failed, still logged in */ }
  };

  const handleLogout = async () => {
    try { await api.logout(); } catch { /* ignore */ }
    clearSessionToken();
    setLoggedIn(false);
    setMerchant(null);
    setPayments([]);
    setPage("dashboard");
  };

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg)" }}>
        <div className="text-center">
          <div className="skeleton w-8 h-8 rounded-full mx-auto mb-3" />
          <p className="text-muted" style={{ fontSize: "var(--text-xs)" }}>Loading...</p>
        </div>
      </div>
    );
  }

  if (!loggedIn) {
    return <Login onLogin={handleLogin} />;
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6" style={{ background: "var(--bg)" }}>
        <div className="text-center auth-card" style={{ maxWidth: "400px" }}>
          <div className="empty-state-icon" style={{ margin: "0 auto var(--space-4)" }}>
            <span style={{ fontSize: "var(--text-lg)" }}>!</span>
          </div>
          <h2 className="page-title" style={{ fontSize: "var(--text-lg)", marginBottom: "var(--space-2)" }}>Unable to connect</h2>
          <p className="text-muted" style={{ marginBottom: "var(--space-5)" }}>
            Could not reach <code>{api.baseUrl}</code>.
            Start your backend server and try again.
          </p>
          <button
            className="btn btn-primary btn-full"
            onClick={() => {
              setError(false);
              setReady(false);
              api.getProfile()
                .then((m) => { setMerchant(m); return api.listPayments(); })
                .then((d) => { setPayments(Array.isArray(d) ? d : []); setReady(true); })
                .catch(() => { setError(true); setReady(true); });
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const pages = {
    dashboard: <Dashboard payments={payments} merchant={merchant} onNavigate={setPage} />,
    payments: <Payments />,
    "qr-payment": <QRPayment />,
    "payment-links": <PaymentLinks />,
    transactions: <Transactions payments={payments} loading={loading} onRefresh={fetchPayments} />,
    "api-integration": <APIIntegration />,
  };

  return (
    <div className="app-shell">
      <Sidebar
        active={page}
        onNavigate={setPage}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        mobileOpen={mobileMenuOpen}
        onMobileClose={() => setMobileMenuOpen(false)}
      />
      <div className={`app-main ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
        <AppHeader
          merchant={merchant}
          onLogout={handleLogout}
          onMobileMenuToggle={() => setMobileMenuOpen(!mobileMenuOpen)}
        />
        <div className="page">
          {pages[page] || pages.dashboard}
        </div>
      </div>
    </div>
  );
}
