// Home.jsx
import React, { useEffect, useState } from "react";
import { WifiOff, Loader2, RotateCw } from "lucide-react";
import PaymentDashboard from "./PaymentDashboard";
import api from "../Api/api";
import "../components/styles/Payment.css";

export default function Home() {
  // "checking" | "online" | "offline"
  const [backendStatus, setBackendStatus] = useState("checking");

  const checkBackend = () => {
    setBackendStatus("checking");
    api
      .ping()
      .then(() => setBackendStatus("online"))
      .catch(() => setBackendStatus("offline"));
  };

  useEffect(() => {
    let cancelled = false;

    api
      .ping()
      .then(() => {
        if (!cancelled) setBackendStatus("online");
      })
      .catch(() => {
        if (!cancelled) setBackendStatus("offline");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (backendStatus === "checking") {
    return (
      <div className="pd-checking-wrap">
        <Loader2 size={15} className="pd-spin" />
        Connecting to till…
      </div>
    );
  }

  if (backendStatus === "offline") {
    return (
      <div className="pd-offline-wrap">
        <div className="pd-offline-card">
          <div className="pd-offline-icon">
            <WifiOff size={22} />
          </div>
          <p className="pd-offline-title">Connection failure</p>
          <p className="pd-offline-text">
            We couldn't reach the payment service. Check your connection and
            try again.
          </p>
          <button className="pd-offline-btn" onClick={checkBackend}>
            <RotateCw size={14} />
            Retry connection
          </button>
        </div>
      </div>
    );
  }

  return <PaymentDashboard />;
}