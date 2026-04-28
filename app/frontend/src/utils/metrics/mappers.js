export function mapCpuChartData(items) {
  return items.map((item, index) => ({
    time: item.time || `${index}`,
    value: (Number(item.cpu_usage) || 0) * 100
  }));
}

export function mapMemoryChartData(items) {
  return items.map((item, index) => ({
    time: item.time || `${index}`,
    value: Number(item.memory_used) || 0
  }));
}

export function mapLoadChartData(items) {
  return items.map((item, index) => ({
    time: item.time || `${index}`,
    value: Number(item.load_avg) || 0
  }));
}

export function mapNetworkChartData(items) {
  return items.map((item, index) => ({
    time: item.time || item.timestamp || item.created_at || `${index}`,
    net_in: Number(item.net_in) || 0,
    net_out: Number(item.net_out) || 0
  }));
}

export function getHistoryItems(metrics) {
  if (!metrics) return [];
  return Array.isArray(metrics) ? metrics : Object.values(metrics);
}