import React from 'react';
import { formatBytes } from '../../utils/metrics/formatters';
import { getUsagePercent } from '../../utils/metrics/calculations';

function MetricProgress({ label, total, used, color = 'primary' }) {
  const percent = getUsagePercent(total, used);

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-1">
        <strong>{label}</strong>
        <span className="text-muted small">
          {formatBytes(used)} / {formatBytes(total)} ({percent.toFixed(2)}%)
        </span>
      </div>

      <div
        className="progress"
        role="progressbar"
        aria-label={label}
        aria-valuenow={percent}
        aria-valuemin="0"
        aria-valuemax="100"
        style={{ height: '10px' }}
      >
        <div
          className={`progress-bar bg-${color}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

export default MetricProgress;