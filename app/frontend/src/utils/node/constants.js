export const NODE_STATIC_FIELDS = [
  'uptime',
  'sysname',
  'version',
  'cpu_num',
  'cpu_model',
  'cpu_sockets',
  'release',
  'boot_mode',
  'pve_version',
  'memory_total',
  'swap_total',
  'disk_total'
];

export const NODE_DYNAMIC_FIELDS = [
  'cpu_usage',
  'memory_used',
  'swap_used',
  'disk_free'
];

export const NODE_METRIC_REQUEST = {
  interval: 'hour',
  cf: 'AVERAGE',
  ds: ['cpu_usage', 'load_avg', 'memory_used', 'net_in', 'net_out']
};

export const NODE_STORAGE_CONTENT_LABELS = {
  iso: 'ISO Images',
  images: 'VM Disks',
  vztmpl: 'CT Templates',
  backup: 'Backups',
  snippets: 'Snippets',
  rootdir: 'CT Volumes'
};