export function normalizeSelectedItem(item) {
  if (!item) return null;

  return {
    ...item,
    status: item.status ?? null,
    host: item.host ?? null,
    platform: item.platform ?? null,
    connected: item.connected ?? null,
    serverId: item.serverId ?? null,
    clusterId: item.clusterId ?? null,
    nodeId: item.nodeId ?? null,
    items: item.items ?? [],
    clusters: item.clusters ?? []
  };
}