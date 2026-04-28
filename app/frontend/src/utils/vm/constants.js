export const VM_CAPABILITY_LABELS = {
  linux24: 'Linux 2.4 kernel',
  linux: 'Linux',
  'windows-modern': 'Windows 10 / Server 2016 / 2019',
  'windows-latest': 'Windows 11 / Server 2022 / 2025',
  other32: 'Other 32-bit',
  other64: 'Other 64-bit',

  empty: 'Without Source',
  iso: 'ISO',
  backup: 'Backup',
  clone: 'Clone',
  template: 'Template',

  scsi: 'SCSI',
  sata: 'SATA',
  ide: 'IDE',
  virtio: 'VirtIO',

  'virtio-scsi-single': 'VirtIO SCSI Single',
  default: 'Default',

  e1000: 'E1000',
  rtl8139: 'RTL8139',
  vmxnet3: 'VMXNET3',

  bios: 'BIOS',
  efi: 'EFI',
  uefi: 'UEFI',
  ovmf: 'OVMF',

  q35: 'Q35',
  i440fx: 'i440fx'
};

export const DEFAULT_DISK = {
  slot: 'scsi0',
  storage_id: '',
  size_gb: 20,
  bus: 'scsi',
  controller_type: 'default',
  backup: true
};

export const DEFAULT_NETWORK = {
  slot: 'net0',
  network_id: '',
  model: 'default',
  connected: true
};

export const DEFAULT_VM = {
  server_id: null,
  node_id: null,
  name: '',
  memory_mb: 2048,
  cpu: {
    cores: 2,
    sockets: 1,
    type: 'host'
  },
  guest: 'other64',
  source: null,
  boot: {
    order: ['scsi0'],
    firmware: 'default',
    machine: 'default',
    secure_boot: false
  },
  disks: [{ ...DEFAULT_DISK }],
  networks: [{ ...DEFAULT_NETWORK }],
  options: {
    autostart: false,
    start_after_create: false,
    graphics: 'default'
  }
};

export const VM_STATIC_FIELDS = [
  'status',
  'uptime',
  'cpu_num',
  'memory_total',
  'disk_total',
  'sysname',
  'agent',
  'ostype'
];

export const VM_DYNAMIC_FIELDS = [
  'cpu_usage',
  'memory_used',
  'memory_free',
  'disk_used',
  'disk_free'
];

export const VM_ACTIONS = [
  { value: 'start', label: 'Start' },
  { value: 'shutdown', label: 'Shutdown' },
  { value: 'stop', label: 'Stop' },
  { value: 'reboot', label: 'Reboot' },
  { value: 'reset', label: 'Reset' },
  { value: 'suspend', label: 'Suspend' },
  { value: 'resume', label: 'Resume' },
];

export const VM_GUEST_OPTIONS = [
  { value: 'linux24', label: 'Linux 2.4 kernel' },
  { value: 'linux', label: 'Linux (modern 2.6+/5.x/6.x)' },
  { value: 'windows-modern', label: 'Windows 10 / Server 2016 / 2019' },
  { value: 'windows-latest', label: 'Windows 11 / Server 2022 / 2025' },
  { value: 'other32', label: 'Other 32-bit' },
  { value: 'other64', label: 'Other 64-bit' }
];

export const VM_GRAPHICS_OPTIONS = [
  { value: 'default', label: 'Default' },
  { value: 'std', label: 'Standard' },
  { value: 'vmvga', label: 'VMVGA' },
  { value: 'virtio', label: 'VirtIO' },
  { value: 'serial0', label: 'Serial' },
  { value: 'none', label: 'None' }
];

export const VM_DISK_BUS_OPTIONS = [
  { value: 'scsi', label: 'SCSI' },
  { value: 'sata', label: 'SATA' },
  { value: 'ide', label: 'IDE' },
  { value: 'virtio', label: 'VirtIO' }
];

export const VM_DISK_CONTROLLER_OPTIONS = [
  { value: 'virtio-scsi-single', label: 'VirtIO SCSI Single' },
  { value: 'paravirtual', label: 'Paravirtual' },
  { value: 'lsi-sas', label: 'LSI SAS' },
  { value: 'nvme', label: 'NVMe' },
  { value: 'default', label: 'Default' }
];