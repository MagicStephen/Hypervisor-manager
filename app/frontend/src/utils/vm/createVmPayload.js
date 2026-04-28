import { getNextDiskSlot, getNextNetworkSlot } from './createVmHelpers';

export function buildPayload(form) {
  const sourceType = form.source?.type ?? 'empty';

  const payload = {
    name: form.name,
    memory_mb: Number(form.memory_mb),
    cpu: {
      cores: Number(form.cpu.cores),
      sockets: Number(form.cpu.sockets),
      ...(form.cpu.type && form.cpu.type !== 'default' ? { type: form.cpu.type } : {})
    }
  };

  if (sourceType !== 'backup') {
    payload.guest = form.guest;
  }

  if (sourceType === 'iso') {
    payload.source = {
      type: 'iso',
      storage_id: form.source.storage_id,
      path: form.source.path
    };
  }

  if (sourceType === 'backup') {
    payload.source = {
      type: 'backup',
      storage_id: form.source.storage_id,
      path: form.source.path
    };

    return payload;
  }

  if (sourceType === 'clone' || sourceType === 'template') {
    payload.source = {
      type: sourceType,
      vmid: Number(form.source.vmid),
      target: {
        storage_id: form.source.target?.storage_id || '',
        full: !!form.source.target?.full
      }
    };
  }

  const disks = form.disks.map((disk, index) => ({
    slot: disk.slot || getNextDiskSlot(form.disks, disk.bus, index),
    storage_id: disk.storage_id,
    size_gb: Number(disk.size_gb),
    bus: disk.bus,
    controller_type: disk.controller_type,
    backup: disk.backup !== false
  }));

  const networks = form.networks.map((nic, index) => ({
    slot: nic.slot || getNextNetworkSlot(form.networks, index),
    network_id: nic.network_id,
    model: nic.model,
    connected: nic.connected !== false
  }));

  payload.disks = disks;
  payload.networks = networks;

  payload.boot = {
    order:
      sourceType === 'iso'
        ? ['ide2', ...(form.boot.order?.filter((x) => x !== 'ide2') || [disks[0]?.slot || 'scsi0'])]
        : form.boot.order?.length
          ? form.boot.order
          : [disks[0]?.slot || 'scsi0'],
    firmware: form.boot.firmware || 'default',
    machine: form.boot.machine || 'default',
    secure_boot: !!form.boot.secure_boot
  };

  payload.options = {
    autostart: !!form.options.autostart,
    start_after_create: !!form.options.start_after_create,
    graphics: form.options.graphics || 'default'
  };

  return payload;
}