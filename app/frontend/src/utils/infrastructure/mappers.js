
function normalizeSelectedItem(item) {
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


export function mapServer(server) {
  return {
    id: server.server_id,
    type: 'server',
    name: server.name,
    host: server.host,
    platform: server.platform.toLowerCase(),
    username: server.username,
    connected: server.connected,
    expanded: false,
    clusters: (server.clusters || []).map((cluster) =>
      mapCluster(cluster, server.server_id, server.platform.toLowerCase())
    )
  };
}


export function mapCluster(cluster, serverId, platform) {
  const clusterId = cluster.cluster || 'Standalone';

  let orphanVms = [];
  let templates = [];

  if (platform === 'xen') {
    orphanVms = (cluster.stopped_vms || []).map((vm) =>
      mapVM(vm, serverId, clusterId, null, platform)
    );

    templates = (cluster.templates || []).map((template) =>
      mapTemplate(template, serverId, clusterId, null, platform)
    );
  }

  return {
    id: clusterId,
    type: 'cluster',
    name: cluster.cluster || 'Standalone',
    expanded: false,
    serverId,
    platform,
    nodes: (cluster.nodes || []).map((node) =>
      mapNode(node, serverId, clusterId, platform)
    ),
    orphanVms,
    templates
  };
}


export function mapNode(node, serverId, clusterId, platform) {
  let mappedItems = [];

  if (platform === 'xen') {
    mappedItems = (node.vms || []).map((vm) =>
      mapVM(vm, serverId, clusterId, node.id, platform)
    );
  } else {
    const mappedVms = (node.vms || []).map((vm) =>
      mapVM(vm, serverId, clusterId, node.id, platform)
    );

    const mappedTemplates = (node.templates || []).map((template) =>
      mapTemplate(template, serverId, clusterId, node.id, platform)
    );

    mappedItems = [...mappedVms, ...mappedTemplates];
  }

  return {
    id: node.id,
    type: 'node',
    name: node.name,
    host: node.host,
    status: node.status,
    expanded: false,
    loading: false,
    vmsLoaded: true,
    serverId,
    clusterId,
    platform,
    networks: node.networks || [],
    items: mappedItems
  };
}


export function mapVM(vm, serverId, clusterId, nodeId = null, platform = null) {
  return {
    id: vm.id,
    type: 'vm',
    name: vm.name,
    status: vm.status,
    serverId,
    clusterId,
    nodeId,
    platform,
    preferredNode: vm.preferred_node ?? null
  };
}


export function mapTemplate(template, serverId, clusterId, nodeId = null, platform = null) {
  return {
    id: template.id,
    type: 'template',
    name: template.name,
    status: template.status,
    serverId,
    clusterId,
    nodeId,
    platform
  };
}