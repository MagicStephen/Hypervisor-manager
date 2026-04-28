import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';

import { formatMetricValue, formatTime, formatDateTime } from '../../utils/metrics/formatters';

import { getLastValidValue } from '../../utils/metrics/calculations';


function MetricChart({
  title,
  data = [],
  dataKey = 'value',
  color = '#0d6efd',
  unit = '',
  height = '100%',
  yDomain,
  series,
}) {
  const isMultiSeries = Array.isArray(series) && series.length > 0;
  const latestValue = !isMultiSeries ? getLastValidValue(data, dataKey) : null;

  return (
    <div className="h-100 d-flex flex-column p-3">
      <div className="d-flex justify-content-between align-items-start mb-2 flex-wrap gap-2">
        <strong>{title}</strong>

        {!isMultiSeries ? (
          <span className="text-muted small">
            {formatMetricValue(latestValue, unit)}
          </span>
        ) : (
          <div className="d-flex gap-3 small text-muted flex-wrap justify-content-end">
            {series.map((s) => {
              const val = getLastValidValue(data, s.dataKey);
              return (
                <span key={s.dataKey}>
                  <strong>{s.name}:</strong> {formatMetricValue(val, unit)}
                </span>
              );
            })}
          </div>
        )}
      </div>

      <div
        className="flex-grow-1"
        style={{
          width: '100%',
          minWidth: 0,
          minHeight: height,
          height,
        }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              {isMultiSeries ? (
                series.map((s) => (
                  <linearGradient
                    key={s.dataKey}
                    id={`gradient-${title}-${s.dataKey}`}
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop offset="0%" stopColor={s.color} stopOpacity={0.35} />
                    <stop offset="100%" stopColor={s.color} stopOpacity={0.05} />
                  </linearGradient>
                ))
              ) : (
                <linearGradient id={`gradient-${title}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={color} stopOpacity={0.05} />
                </linearGradient>
              )}
            </defs>

            <CartesianGrid strokeDasharray="3 3" vertical={false} />

            <XAxis
              dataKey="time"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={formatTime}
            />

            <YAxis
              domain={yDomain || ['auto', 'auto']}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={70}
              tickFormatter={(value) => formatMetricValue(value, unit, true)}
            />

            <Tooltip
              formatter={(value, name) => [formatMetricValue(value, unit), name]}
              labelFormatter={(label) => `Čas: ${formatDateTime(label)}`}
            />

            {isMultiSeries ? (
              series.map((s) => (
                <Area
                  key={s.dataKey}
                  type="monotone"
                  dataKey={s.dataKey}
                  name={s.name}
                  stroke={s.color}
                  fill={`url(#gradient-${title}-${s.dataKey})`}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 3 }}
                  connectNulls
                />
              ))
            ) : (
              <Area
                type="monotone"
                dataKey={dataKey}
                stroke={color}
                fill={`url(#gradient-${title})`}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3 }}
                connectNulls
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default MetricChart;