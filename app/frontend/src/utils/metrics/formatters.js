const BYTE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB'];

export function formatBytes(bytes, decimals = 2, fixedUnit = 'GB') {
  if (bytes == null || Number.isNaN(Number(bytes))) return '-';

  const value = Number(bytes);

  if (fixedUnit === 'GB') {
    return `${(value / (1024 ** 3)).toFixed(decimals)} GB`;
  }

  let size = value;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < BYTE_UNITS.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }

  return `${size.toFixed(decimals)} ${BYTE_UNITS[unitIndex]}`;
}

export function formatUptime(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds)) || seconds < 0) return '-';

  const totalSeconds = Math.floor(Number(seconds));
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  if (days > 0) {
    return `${days}d ${String(hours).padStart(2, '0')}h ${String(minutes).padStart(2, '0')}m ${String(secs).padStart(2, '0')}s`;
  }

  return `${String(hours).padStart(2, '0')}h ${String(minutes).padStart(2, '0')}m ${String(secs).padStart(2, '0')}s`;
}

export function formatMetricValue(value, unit = '', forAxis = false) {
  if (value == null || Number.isNaN(Number(value))) return '-';

  const number = Number(value);

  if (unit === 'percent') return `${number.toFixed(1)} %`;
  if (unit === 'load') return number.toFixed(1);
  if (unit === 'memory_gb') return formatBytes(number, forAxis ? 1 : 2, 'GB');
  if (unit === 'bytes') return formatBytes(number, forAxis ? 0 : 2, 'auto');

  if (unit === 'traffic') {
    if (number < 1024) return `${number.toFixed(2)} B/s`;
    if (number < 1024 ** 2) return `${(number / 1024).toFixed(forAxis ? 0 : 2)} KB/s`;
    if (number < 1024 ** 3) return `${(number / (1024 ** 2)).toFixed(forAxis ? 0 : 2)} MB/s`;
    return `${(number / (1024 ** 3)).toFixed(forAxis ? 1 : 2)} GB/s`;
  }

  return number.toFixed(2);
}

export function formatTime(value) {
  if (!value) return '-';

  return new Date(value * 1000).toLocaleTimeString('cs-CZ', {
    hour: '2-digit',
    minute: '2-digit'
  });
}

export function formatDateTime(value) {
  if (!value) return '-';

  return new Date(value * 1000).toLocaleString('cs-CZ', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

export function formatDateTimeSafe(value) {
  if (value == null) return '-';

  const numeric = Number(value);
  const date = new Date(numeric < 1000000000000 ? numeric * 1000 : numeric);

  if (Number.isNaN(date.getTime())) return String(value);

  return date.toLocaleString('cs-CZ');
}