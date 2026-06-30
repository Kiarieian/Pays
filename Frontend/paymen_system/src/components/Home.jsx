// Home.jsx
import React, { useEffect, useState } from "react";
import PaymentDashboard from "./PaymentDashboard";
import api from "../Api/api"
export default function Home() {
  // "checking" | "online" | "offline"
  const [backendStatus, setBackendStatus] = useState("checking");

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

  if (backendStatus === "offline") {
    return (
      <div
        className="min-h-screen w-full flex items-center justify-center px-6"
        style={{ background: "#06140c", color: "#EAF5EE" }}
      >
        <div
          className="max-w-sm w-full rounded-2xl p-6 text-center"
          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
        >
          <p className="text-lg font-semibold mb-2">Backend not reachable</p>
          <p className="text-sm text-white/50 mb-4">
            Couldn't connect to <span className="font-mono text-white/70">{api.baseUrl}</span>.
            Make sure your FastAPI server is running and that CORS is enabled for this origin.
          </p>
          <button
            onClick={() => {
              setBackendStatus("checking");
              api
                .ping()
                .then(() => setBackendStatus("online"))
                .catch(() => setBackendStatus("offline"));
            }}
            className="px-4 py-2 rounded-lg text-sm font-medium"
            style={{ background: "linear-gradient(135deg, #9AE600, #00A651)", color: "#06140c" }}
          >
            Retry connection
          </button>
        </div>
      </div>
    );
  }

  return <PaymentDashboard />;
}