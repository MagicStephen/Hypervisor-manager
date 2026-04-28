import { DEFAULT_VM, VM_CAPABILITY_LABELS } from './constants';

export function formatCapabilityLabel(value) {
  return VM_CAPABILITY_LABELS[value] || value;
}

export function cloneVmWithRuntime(serverId, nodeId) {
  return {
    ...structuredClone(DEFAULT_VM),
    server_id: serverId ?? null,
    node_id: nodeId ?? null
  };
}

export function recalculateVcpus(vm) {
  const cores = Number(vm.cpu?.cores) || 0;
  const sockets = Number(vm.cpu?.sockets) || 0;

  return {
    ...vm,
    cpu: {
      ...vm.cpu,
      vcpus: cores * sockets
    }
  };
}

export function createSourceByType(type) {
  switch (type) {
    case 'iso':
      return { type: 'iso', storage_id: '', path: '' };
    case 'backup':
      return { type: 'backup', storage_id: '', path: '' };
    case 'clone':
      return { type: 'clone', vmid: null, target: { storage_id: '', full: true } };
    case 'template':
      return { type: 'template', vmid: null, target: { storage_id: '', full: true } };
    default:
      return null;
  }
}

export function getDiskSlotPrefix(bus) {
  if (bus === 'ide') return 'ide';
  if (bus === 'sata') return 'sata';
  if (bus === 'virtio') return 'virtio';
  return 'scsi';
}

export function getNextDiskSlot(disks, bus, excludeIndex = null) {
  const prefix = getDiskSlotPrefix(bus);

  const usedIndexes = disks
    .map((disk, index) => ({ disk, index }))
    .filter(({ index }) => index !== excludeIndex)
    .map(({ disk }) => disk?.slot)
    .filter((slot) => typeof slot === 'string' && slot.startsWith(prefix))
    .map((slot) => Number(slot.replace(prefix, '')))
    .filter((n) => Number.isInteger(n) && n >= 0);

  let next = 0;

  while (usedIndexes.includes(next)) {
    next += 1;
  }

  return `${prefix}${next}`;
}

export function getNextNetworkSlot(networks, excludeIndex = null) {
  const usedIndexes = networks
    .map((nic, index) => ({ nic, index }))
    .filter(({ index }) => index !== excludeIndex)
    .map(({ nic }) => nic?.slot)
    .filter((slot) => typeof slot === 'string' && slot.startsWith('net'))
    .map((slot) => Number(slot.replace('net', '')))
    .filter((n) => Number.isInteger(n) && n >= 0);

  let next = 0;

  while (usedIndexes.includes(next)) {
    next += 1;
  }

  return `net${next}`;
}

export function getBusFromSlot(slot) {
  if (!slot || typeof slot !== 'string') return 'scsi';
  if (slot.startsWith('ide')) return 'ide';
  if (slot.startsWith('sata')) return 'sata';
  if (slot.startsWith('virtio')) return 'virtio';
  return 'scsi';
}

export function storageHasContent(storage, type) {
  const content = storage?.content;

  if (Array.isArray(content)) return content.includes(type);

  if (typeof content === 'string') {
    return content
      .split(',')
      .map((item) => item.trim())
      .includes(type);
  }

  return false;
}

export function getNetworkValue(network) {
  return network?.id || network?.network_id || network?.bridge || network?.iface || '';
}

export function getNetworkLabel(network, index) {
  return (
    network?.name ||
    network?.label ||
    network?.bridge ||
    network?.iface ||
    getNetworkValue(network) ||
    `Network ${index + 1}`
  );
}