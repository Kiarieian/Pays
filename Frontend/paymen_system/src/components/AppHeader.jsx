import React from "react";
import { Menu, LogOut } from "lucide-react";

export default function AppHeader({ merchant, onLogout, onMobileMenuToggle }) {
  return (
    <header className="app-header">
      <div className="header-left">
        <button className="mobile-menu-button" onClick={onMobileMenuToggle}>
          <Menu size={18} />
        </button>
        <div className="header-status">
          <span className="header-status-dot" />
          <span>Connected</span>
        </div>
      </div>

      <div className="header-right">
        {merchant && (
          <div className="header-merchant">
            <div className="header-merchant-name">{merchant.business_name || "Merchant"}</div>
            {merchant.merchant_code && (
              <div className="header-merchant-id">{merchant.merchant_code}</div>
            )}
          </div>
        )}

        <button className="profile-button" onClick={onLogout} title="Log out">
          <div className="profile-avatar">
            {(merchant?.business_name || "M").charAt(0).toUpperCase()}
          </div>
          <LogOut size={15} className="text-muted" />
        </button>
      </div>
    </header>
  );
}
