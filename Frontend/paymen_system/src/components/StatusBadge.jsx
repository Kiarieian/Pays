import React from "react";

const STYLES = {
  SUCCESS: "status-success",
  PENDING: "status-warning",
  FAILED: "status-error",
  TIMEOUT: "status-error",
};

const LABELS = {
  SUCCESS: "Successful",
  PENDING: "Pending",
  FAILED: "Failed",
  TIMEOUT: "Timed out",
};

export default function StatusBadge({ status }) {
  const className = STYLES[status] || "status-warning";
  const label = LABELS[status] || status;

  return (
    <span className={`status ${className}`}>
      <span className="status-dot" />
      {label}
    </span>
  );
}
