import React, { useEffect, useMemo, useState } from 'react';
import Spinner from '../Common/Spinner';
import { CreateVm, fetchVmConfiguration, fetchVmCapabilities } from '../../services/VmService';
import {
  fetchNodeStorage,
  fetchNodeStorageContent,
  fetchNodeNetworks
} from '../../services/NodeService';

import { DEFAULT_DISK } from '../../utils/vm/constants';

import {
  formatCapabilityLabel,
  cloneVmWithRuntime,
  recalculateVcpus,
  createSourceByType,
  getNextDiskSlot,
  getBusFromSlot,
  storageHasContent,
  getNetworkValue,
  getNetworkLabel
} from '../../utils/vm/createVmHelpers';

import { buildPayload } from '../../utils/vm/createVmPayload';

function NodeCreateVm({
  serverId,
  nodeId,
  templates = [],
}) {

  const [form, setForm] = useState(() =>
    recalculateVcpus(cloneVmWithRuntime(serverId, nodeId))
  );

  const [capabilities, setCapabilities] = useState(null);
  const [capabilitiesLoading, setCapabilitiesLoading] = useState(false);

  const [storages, setStorages] = useState([]);
  const [storageLoading, setStorageLoading] = useState(false);

  const [nodeNetworks, setNodeNetworks] = useState([]);
  const [networksLoading, setNetworksLoading] = useState(false);

  const [backupFilesByStorage, setBackupFilesByStorage] = useState({});
  const [backupLoading, setBackupLoading] = useState(false);

  const [isoFilesByStorage, setIsoFilesByStorage] = useState({});
  const [isoLoading, setIsoLoading] = useState(false);

  const [templateConfig, setTemplateConfig] = useState(null);
  const [templateConfigLoading, setTemplateConfigLoading] = useState(false);

  const [loading, setLoading] = useState(false);
  const [resultMessage, setResultMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const sourceType = form.source?.type ?? 'empty';

  const sourceTypes = capabilities?.source_types || [];
  const guestTypes = capabilities?.guest?.types || [];
  const diskBuses = capabilities?.disk?.buses || [];
  const diskControllers = capabilities?.disk?.controllers || [];
  const networkModels = capabilities?.network?.models || [];
  const bootFirmwares = capabilities?.boot?.firmware || [];
  const bootMachines = capabilities?.boot?.machines || [];
  const graphicsModels = capabilities?.graphics?.models || [];

  const totalVcpus = useMemo(() => {
    const cores = Number(form.cpu?.cores) || 0;
    const sockets = Number(form.cpu?.sockets) || 0;
    return cores * sockets;
  }, [form.cpu?.cores, form.cpu?.sockets]);

  const isoCapableStorages = useMemo(() => {
    return storages.filter((storage) => storageHasContent(storage, 'iso'));
  }, [storages]);

  const diskStorages = useMemo(() => {
    return storages.filter(
      (storage) =>
        storageHasContent(storage, 'images') || storageHasContent(storage, 'rootdir')
    );
  }, [storages]);

  const backupStorages = useMemo(() => {
    return storages.filter((storage) => storageHasContent(storage, 'backup'));
  }, [storages]);

  const availableIsoFiles = useMemo(() => {
    if (sourceType !== 'iso' || !form.source?.storage_id) return [];
    return isoFilesByStorage[form.source.storage_id] || [];
  }, [sourceType, form.source, isoFilesByStorage]);

  const availableBackupFiles = useMemo(() => {
    if (sourceType !== 'backup' || !form.source?.storage_id) return [];
    return backupFilesByStorage[form.source.storage_id] || [];
  }, [sourceType, form.source, backupFilesByStorage]);

  const availableTemplates = useMemo(() => {
    return templates.filter((template) => {
      const sameServer = template.serverId === serverId;
      const sameNode = template.nodeId === nodeId;
      return sameServer && sameNode;
    });
  }, [templates, serverId, nodeId]);

  const availableNetworks = useMemo(() => {
    return Array.isArray(nodeNetworks)
      ? nodeNetworks.filter((net) => net.active !== false)
      : [];
  }, [nodeNetworks]);

  const defaultNetworkId = useMemo(() => {
    const defaultNetwork =
      availableNetworks.find((net) => net.default) || availableNetworks[0] || null;

    return getNetworkValue(defaultNetwork);
  }, [availableNetworks]);

  const isSubmitDisabled = useMemo(() => {
    if (
      serverId == null ||
      nodeId == null ||
      !form.name ||
      loading ||
      templateConfigLoading ||
      capabilitiesLoading ||
      !capabilities
    ) {
      return true;
    }

    if (sourceType === 'iso') {
      if (!form.source?.storage_id || !form.source?.path) return true;
    }

    if (sourceType === 'backup') {
      if (!form.source?.storage_id || !form.source?.path) return true;
      return false;
    }

    if (sourceType === 'clone' || sourceType === 'template') {
      if (!form.source?.vmid) return true;
    }

    if (sourceType !== 'backup' && sourceType !== 'clone') {
      if (!form.networks?.length || !form.networks[0]?.network_id) return true;
      if (!form.disks.length) return true;

    const invalidDisk = form.disks.some(
        (disk) => !disk.storage_id || !disk.size_gb || Number(disk.size_gb) <= 0
      );

      if (invalidDisk) return true;
    }

    return false;
  }, [
    serverId,
    nodeId,
    form,
    loading,
    sourceType,
    templateConfigLoading,
    capabilitiesLoading,
    capabilities,
  ]);

  async function loadCapabilities() {
    try {
      setCapabilitiesLoading(true);

      const result = await fetchVmCapabilities(serverId, nodeId);
      setCapabilities(result || null);
    } catch (error) {
      console.error('Error loading VM capabilities:', error);
      setCapabilities(null);
      setErrorMessage('Při načítání capabilities došlo k chybě.');
    } finally {
      setCapabilitiesLoading(false);
    }
  }

  async function loadStorages() {
    try {
      setStorageLoading(true);

      const result = await fetchNodeStorage(serverId, nodeId);
      const storageData = result || [];
      const normalized = Array.isArray(storageData) ? storageData : [];

      setStorages(normalized);

      setForm((prev) => {
        const next = structuredClone(prev);

        if (!next.disks[0]?.storage_id) {
          const firstDiskStorage = normalized.find(
            (s) => storageHasContent(s, 'images') || storageHasContent(s, 'rootdir')
          );

          if (firstDiskStorage) {
            next.disks[0].storage_id = firstDiskStorage.storage_id;
          }
        }

        if (next.source?.type === 'iso' && !next.source.storage_id) {
          const firstIsoStorage = normalized.find((s) => storageHasContent(s, 'iso'));

          if (firstIsoStorage) {
            next.source.storage_id = firstIsoStorage.storage_id;
          }
        }

        return next;
      });
    } catch (error) {
      console.error('Error loading storages:', error);
      setStorages([]);
    } finally {
      setStorageLoading(false);
    }
  }

  async function loadNetworks() {
    try {
      setNetworksLoading(true);

      const result = await fetchNodeNetworks(serverId, nodeId);
      const networkData = result || [];
      const normalized = Array.isArray(networkData) ? networkData : [];

      setNodeNetworks(normalized);
    } catch (error) {
      console.error('Error loading networks:', error);
      setNodeNetworks([]);
    } finally {
      setNetworksLoading(false);
    }
  }

  async function loadIsoFiles(storageId) {
    if (!storageId || isoFilesByStorage[storageId]) return;

    try {
      setIsoLoading(true);

      const result = await fetchNodeStorageContent(serverId, nodeId, storageId);
      const filesData = result || [];

      const isoFiles = (Array.isArray(filesData) ? filesData : []).filter(
        (file) => file.content === 'iso'
      );

      setIsoFilesByStorage((prev) => ({
        ...prev,
        [storageId]: isoFiles,
      }));
    } catch (error) {
      console.error('Error loading ISO files:', error);
      setIsoFilesByStorage((prev) => ({
        ...prev,
        [storageId]: [],
      }));
    } finally {
      setIsoLoading(false);
    }
  }

  async function loadBackupFiles(storageId) {
    if (!storageId || backupFilesByStorage[storageId]) return;

    try {
      setBackupLoading(true);

      const result = await fetchNodeStorageContent(serverId, nodeId, storageId);
      const filesData = result || [];

      const backupFiles = (Array.isArray(filesData) ? filesData : []).filter(
        (file) => file.content === 'backup'
      );

      setBackupFilesByStorage((prev) => ({
        ...prev,
        [storageId]: backupFiles,
      }));
    } catch (error) {
      console.error('Error loading backup files:', error);
      setBackupFilesByStorage((prev) => ({
        ...prev,
        [storageId]: [],
      }));
    } finally {
      setBackupLoading(false);
    }
  }

  async function loadTemplateConfiguration(templateVmid) {
    try {
      setTemplateConfigLoading(true);
      setErrorMessage('');

      const result = await fetchVmConfiguration(serverId, nodeId, templateVmid);
      const config = result || null;

      setTemplateConfig(config);

      setForm((prev) => {
        const next = structuredClone(prev);

        next.source = {
          ...next.source,
          vmid: templateVmid,
        };

        if (config?.memory_mb != null) {
          next.memory_mb = Number(config.memory_mb);
        }

        if (config?.cpu?.cores != null) {
          next.cpu.cores = Number(config.cpu.cores);
        }

        if (config?.cpu?.sockets != null) {
          next.cpu.sockets = Number(config.cpu.sockets);
        }

        if (config?.cpu?.type) {
          next.cpu.type = config.cpu.type;
        }

        if (config?.guest && guestTypes.includes(config.guest)) {
          next.guest = config.guest;
        }

        if (Array.isArray(config?.disks) && config.disks.length > 0) {
          next.disks = config.disks.map((disk, index) => {
            const busFromSlot = getBusFromSlot(disk.slot);
            const bus = diskBuses.includes(busFromSlot)
              ? busFromSlot
              : capabilities?.disk?.default_bus || diskBuses[0] || 'scsi';

            return {
              slot: disk.slot || getNextDiskSlot(config.disks, bus, index),
              storage_id: disk.storage_id || '',
              size_gb: Number(disk.size_gb ?? 20),
              bus,
              controller_type: diskControllers.includes(disk.controller_type)
                ? disk.controller_type
                : capabilities?.disk?.default_controller || diskControllers[0] || 'default',
              backup: true,
            };
          });
        }

        if (Array.isArray(config?.networks) && config.networks.length > 0) {
          next.networks = config.networks.map((nic, index) => ({
            slot: nic.slot || `net${index}`,
            network_id: nic.network_id || '',
            model: networkModels.includes(nic.model)
              ? nic.model
              : capabilities?.network?.default_model || networkModels[0] || 'default',
            connected: nic.connected !== false,
          }));
        }

        if (config?.boot) {
          next.boot = {
            ...next.boot,
            order:
              Array.isArray(config.boot.order) && config.boot.order.length > 0
                ? config.boot.order
                : next.boot.order,
            firmware: bootFirmwares.includes(config.boot.firmware)
              ? config.boot.firmware
              : next.boot.firmware,
            machine: bootMachines.includes(config.boot.machine)
              ? config.boot.machine
              : next.boot.machine,
            secure_boot: !!capabilities?.boot?.secure_boot && !!config.boot.secure_boot,
          };
        }

        if (config?.options) {
          next.options = {
            ...next.options,
            autostart: !!config.options.autostart,
            start_after_create: !!config.options.start_after_create,
            graphics: graphicsModels.includes(config.options.graphics)
              ? config.options.graphics
              : next.options.graphics,
          };
        }

        return recalculateVcpus(next);
      });
    } catch (error) {
      console.error('Error loading template config:', error);
      setTemplateConfig(null);
      setErrorMessage('Při načítání konfigurace templatu došlo k chybě.');
    } finally {
      setTemplateConfigLoading(false);
    }
  }

  function setField(name, value) {
    setForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  }

  function setNumberField(name, value) {
    setForm((prev) => ({
      ...prev,
      [name]: value === '' ? '' : Number(value),
    }));
  }

  function setCpuField(name, value) {
    setForm((prev) =>
      recalculateVcpus({
        ...prev,
        cpu: {
          ...prev.cpu,
          [name]: value === '' ? '' : Number(value),
        },
      })
    );
  }

  function setSourceType(type) {
    setTemplateConfig(null);

    setForm((prev) => ({
      ...prev,
      source: createSourceByType(type),
      boot: {
        ...prev.boot,
        order:
          type === 'iso'
            ? ['ide2', prev.disks[0]?.slot || 'scsi0']
            : [prev.disks[0]?.slot || 'scsi0'],
      },
    }));
  }

  function setSourceValue(name, value) {
    setForm((prev) => ({
      ...prev,
      source: {
        ...prev.source,
        [name]: value,
      },
    }));
  }

  function setSourceTargetValue(name, value) {
    setForm((prev) => ({
      ...prev,
      source: {
        ...prev.source,
        target: {
          ...prev.source.target,
          [name]: value,
        },
      },
    }));
  }

  function setBootField(name, value) {
    setForm((prev) => ({
      ...prev,
      boot: {
        ...prev.boot,
        [name]: value,
      },
    }));
  }

  function setOptionField(name, value) {
    setForm((prev) => ({
      ...prev,
      options: {
        ...prev.options,
        [name]: value,
      },
    }));
  }

  function setPrimaryNetworkField(name, value) {
    setForm((prev) => ({
      ...prev,
      networks: prev.networks.map((network, index) =>
        index === 0
          ? {
              ...network,
              [name]: value,
            }
          : network
      ),
    }));
  }

  function handleDiskChange(index, field, value) {
    setForm((prev) => {
      const nextDisks = prev.disks.map((disk, i) => {
        if (i !== index) return disk;

        const updatedDisk = {
          ...disk,
          [field]: field === 'size_gb' ? (value === '' ? '' : Number(value)) : value,
        };

        if (field === 'bus') {
          updatedDisk.slot = getNextDiskSlot(prev.disks, value, index);
        }

        return updatedDisk;
      });

      return {
        ...prev,
        disks: nextDisks,
        boot: {
          ...prev.boot,
          order: prev.boot.order?.length
            ? prev.boot.order.map((item) =>
                item === prev.disks[index]?.slot ? nextDisks[index].slot : item
              )
            : prev.boot.order,
        },
      };
    });
  }

  function handleAddDisk() {
    const defaultStorageId = diskStorages[0]?.storage_id || '';
    const defaultBus = capabilities?.disk?.default_bus || diskBuses[0] || 'scsi';
    const defaultController =
      capabilities?.disk?.default_controller || diskControllers[0] || 'default';

    setForm((prev) => {
      const newSlot = getNextDiskSlot(prev.disks, defaultBus);

      return {
        ...prev,
        disks: [
          ...prev.disks,
          {
            ...DEFAULT_DISK,
            storage_id: defaultStorageId,
            bus: defaultBus,
            controller_type: defaultController,
            slot: newSlot,
          },
        ],
      };
    });
  }

  function handleRemoveDisk(index) {
    setForm((prev) => {
      if (prev.disks.length <= 1) return prev;

      const removedSlot = prev.disks[index]?.slot;

      return {
        ...prev,
        disks: prev.disks.filter((_, i) => i !== index),
        boot: {
          ...prev.boot,
          order: prev.boot.order.filter((item) => item !== removedSlot),
        },
      };
    });
  }

  async function handleSubmit(e) {
    e.preventDefault();

    setResultMessage('');
    setErrorMessage('');

    try {
      setLoading(true);

      const payload = buildPayload(form);
      const result = await CreateVm(serverId, nodeId, payload);

      setResultMessage(result?.message || 'VM bylo úspěšně vytvořeno.');
      setTemplateConfig(null);

      const resetForm = recalculateVcpus(cloneVmWithRuntime(serverId, nodeId));

      if (capabilities) {
        resetForm.guest = capabilities.guest?.default || guestTypes[0] || resetForm.guest;
        resetForm.disks[0].bus = capabilities.disk?.default_bus || diskBuses[0] || 'scsi';
        resetForm.disks[0].controller_type =
          capabilities.disk?.default_controller || diskControllers[0] || 'default';
        resetForm.disks[0].slot = getNextDiskSlot([], resetForm.disks[0].bus);
        resetForm.networks[0].model =
          capabilities.network?.default_model || networkModels[0] || 'default';
        resetForm.boot.firmware = bootFirmwares[0] || 'default';
        resetForm.boot.machine = bootMachines[0] || 'default';
        resetForm.options.graphics = capabilities.graphics?.default || graphicsModels[0] || 'default';
        resetForm.options.start_after_create = !!capabilities.options?.start_after_create;
      }

      if (defaultNetworkId) {
        resetForm.networks[0].network_id = defaultNetworkId;
      }

      setForm(resetForm);
    } catch (error) {
      console.error('Error creating VM:', error);
      setErrorMessage('Při vytváření VM došlo k chybě.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!serverId || !nodeId) {
      setCapabilities(null);
      return;
    }

    loadCapabilities();
  }, [serverId, nodeId]);

  useEffect(() => {
    if (!capabilities) return;

    setForm((prev) => {
      const next = structuredClone(prev);

      const defaultGuest = capabilities.guest?.default || guestTypes[0] || 'other64';
      const defaultBus = capabilities.disk?.default_bus || diskBuses[0] || 'scsi';
      const defaultController = capabilities.disk?.default_controller || diskControllers[0] || 'default';
      const defaultNetworkModel = capabilities.network?.default_model || networkModels[0] || 'default';
      const defaultFirmware = bootFirmwares[0] || 'default';
      const defaultMachine = bootMachines[0] || 'default';
      const defaultGraphics = capabilities.graphics?.default || graphicsModels[0] || 'default';

      next.guest = guestTypes.includes(next.guest) ? next.guest : defaultGuest;

      next.disks = next.disks.map((disk, index) => {
        const bus = diskBuses.includes(disk.bus) ? disk.bus : defaultBus;

        return {
          ...disk,
          bus,
          slot: disk.slot || getNextDiskSlot(next.disks, bus, index),
          controller_type: diskControllers.includes(disk.controller_type)
            ? disk.controller_type
            : defaultController,
        };
      });

      next.networks = next.networks.map((nic) => ({
        ...nic,
        model: networkModels.includes(nic.model) ? nic.model : defaultNetworkModel,
      }));

      next.boot = {
        ...next.boot,
        firmware: bootFirmwares.includes(next.boot.firmware)
          ? next.boot.firmware
          : defaultFirmware,
        machine: bootMachines.includes(next.boot.machine)
          ? next.boot.machine
          : defaultMachine,
        secure_boot: !!capabilities.boot?.secure_boot && !!next.boot.secure_boot,
      };

      next.options = {
        ...next.options,
        start_after_create: !!capabilities.options?.start_after_create,
        graphics: graphicsModels.includes(next.options.graphics)
          ? next.options.graphics
          : defaultGraphics,
      };

      return recalculateVcpus(next);
    });
  }, [capabilities]);

  useEffect(() => {
    if (!sourceTypes.length) return;

    const current = form.source?.type ?? 'empty';

    if (!sourceTypes.includes(current)) {
      setSourceType(sourceTypes[0]);
    }
  }, [sourceTypes, form.source?.type]);

  useEffect(() => {
    if (!serverId || !nodeId) {
      setStorages([]);
      return;
    }

    loadStorages();
  }, [serverId, nodeId]);

  useEffect(() => {
    if (!serverId || !nodeId) {
      setNodeNetworks([]);
      return;
    }

    loadNetworks();
  }, [serverId, nodeId]);

  useEffect(() => {
    if (!defaultNetworkId) return;

    setForm((prev) => {
      const currentNetworkId = prev.networks?.[0]?.network_id;

      if (currentNetworkId) {
        return prev;
      }

      return {
        ...prev,
        networks: prev.networks.map((network, index) =>
          index === 0
            ? {
                ...network,
                network_id: defaultNetworkId,
              }
            : network
        ),
      };
    });
  }, [defaultNetworkId]);

  useEffect(() => {
    if (!resultMessage && !errorMessage) return;

    const timeoutId = setTimeout(() => {
      setResultMessage('');
      setErrorMessage('');
    }, 3000);

    return () => clearTimeout(timeoutId);
  }, [resultMessage, errorMessage]);

  useEffect(() => {
    if (sourceType !== 'iso' || !form.source?.storage_id) return;
    loadIsoFiles(form.source.storage_id);
  }, [sourceType, form.source?.storage_id]);

  useEffect(() => {
    if (sourceType !== 'backup' || !form.source?.storage_id) return;
    loadBackupFiles(form.source.storage_id);
  }, [sourceType, form.source?.storage_id]);

  useEffect(() => {
    if (sourceType !== 'template' || !form.source?.vmid || !serverId || !nodeId) {
      setTemplateConfig(null);
      return;
    }

    loadTemplateConfiguration(form.source.vmid);
  }, [sourceType, form.source?.vmid, serverId, nodeId]);

  return (
    <div className="col-12 h-100">
      <div className="card h-100 w-100">
        <div className="card-body overflow-auto position-relative p-3">
          <Spinner
            loading={
              loading ||
              storageLoading ||
              networksLoading ||
              templateConfigLoading ||
              capabilitiesLoading
            }
          />

          {resultMessage && (
            <div className="alert alert-success py-2 mb-2" role="alert">
              {resultMessage}
            </div>
          )}

          {errorMessage && (
            <div className="alert alert-danger py-2 mb-2" role="alert">
              {errorMessage}
            </div>
          )}

          {!capabilities && !capabilitiesLoading && (
            <div className="alert alert-warning py-2 mb-2" role="alert">
              Capabilities nejsou načtené.
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="row g-2">
              <div className="col-lg-9">
                <label className="form-label small mb-1">Name *</label>
                <input
                  type="text"
                  className="form-control form-control-sm"
                  value={form.name}
                  onChange={(e) => setField('name', e.target.value)}
                  placeholder="např. ubuntu-test"
                  required
                />
              </div>

              <div className="col-lg-3">
                <label className="form-label small mb-1">Memory (MB)</label>
                <input
                  type="number"
                  className="form-control form-control-sm"
                  value={form.memory_mb}
                  onChange={(e) => setNumberField('memory_mb', e.target.value)}
                  min="256"
                  step="256"
                />
              </div>

              <div className="col-lg-3">
                <label className="form-label small mb-1">CPU cores</label>
                <input
                  type="number"
                  className="form-control form-control-sm"
                  value={form.cpu.cores}
                  onChange={(e) => setCpuField('cores', e.target.value)}
                  min="1"
                />
              </div>

              <div className="col-lg-3">
                <label className="form-label small mb-1">CPU sockets</label>
                <input
                  type="number"
                  className="form-control form-control-sm"
                  value={form.cpu.sockets}
                  onChange={(e) => setCpuField('sockets', e.target.value)}
                  min="1"
                />
              </div>

              <div className="col-lg-3">
                <label className="form-label small mb-1">Total vCPU</label>
                <input
                  type="text"
                  className="form-control form-control-sm"
                  value={form.cpu.vcpus ?? totalVcpus}
                  disabled
                />
              </div>

              <div className="col-lg-6">
                <label className="form-label small mb-1">Guest OS</label>
                <select
                  className="form-select form-select-sm"
                  value={form.guest}
                  onChange={(e) => setField('guest', e.target.value)}
                  disabled={!guestTypes.length}
                >
                  {guestTypes.map((guest) => (
                    <option key={guest} value={guest}>
                      {formatCapabilityLabel(guest)}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <hr className="my-2" />

            <div className="row g-2 align-items-end mb-2">
              <div className="col-lg-3">
                <label className="form-label small mb-1">Boot medium</label>
                <select
                  className="form-select form-select-sm"
                  value={sourceType}
                  onChange={(e) => setSourceType(e.target.value)}
                  disabled={!sourceTypes.length}
                >
                  {sourceTypes.map((type) => (
                    <option key={type} value={type}>
                      {formatCapabilityLabel(type)}
                    </option>
                  ))}
                </select>
              </div>

              {sourceType === 'iso' && (
                <>
                  <div className="col-lg-3">
                    <label className="form-label small mb-1">ISO Storage</label>
                    <select
                      className="form-select form-select-sm"
                      value={form.source?.storage_id || ''}
                      onChange={(e) => {
                        const value = e.target.value;

                        setForm((prev) => ({
                          ...prev,
                          source: {
                            ...prev.source,
                            storage_id: value,
                            path: '',
                          },
                        }));
                      }}
                    >
                      <option value="">Vyber storage</option>
                      {isoCapableStorages.map((storage) => (
                        <option key={storage.storage_id} value={storage.storage_id}>
                          {storage.storage || storage.storage_id}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="col-lg-4">
                    <label className="form-label small mb-1">ISO file</label>
                    <select
                      className="form-select form-select-sm"
                      value={form.source?.path || ''}
                      onChange={(e) => setSourceValue('path', e.target.value)}
                      disabled={!form.source?.storage_id || isoLoading}
                    >
                      <option value="">
                        {isoLoading ? 'Načítám ISO...' : 'Vyber ISO'}
                      </option>

                      {availableIsoFiles.map((file) => (
                        <option
                          key={file.volid || file.name}
                          value={file.name || file.volid}
                        >
                          {file.name || file.volid}
                        </option>
                      ))}
                    </select>
                  </div>
                </>
              )}

              {sourceType === 'backup' && (
                <>
                  <div className="col-lg-3">
                    <label className="form-label small mb-1">Backup Storage</label>
                    <select
                      className="form-select form-select-sm"
                      value={form.source?.storage_id || ''}
                      onChange={(e) => {
                        const value = e.target.value;

                        setForm((prev) => ({
                          ...prev,
                          source: {
                            ...prev.source,
                            storage_id: value,
                            path: '',
                          },
                        }));
                      }}
                    >
                      <option value="">Vyber storage</option>
                      {backupStorages.map((storage) => (
                        <option key={storage.storage_id} value={storage.storage_id}>
                          {storage.storage || storage.storage_id}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="col-lg-6">
                    <label className="form-label small mb-1">Backup file</label>
                    <select
                      className="form-select form-select-sm"
                      value={form.source?.path || ''}
                      onChange={(e) => setSourceValue('path', e.target.value)}
                      disabled={!form.source?.storage_id || backupLoading}
                    >
                      <option value="">
                        {backupLoading ? 'Načítám backupy...' : 'Vyber backup'}
                      </option>

                      {availableBackupFiles.map((file) => (
                        <option
                          key={file.volid || file.name}
                          value={file.name || file.volid}
                        >
                          {file.name || file.volid}
                        </option>
                      ))}
                    </select>
                  </div>
                </>
              )}

              {sourceType === 'clone' && (
                <>
                  <div className="col-lg-3">
                    <label className="form-label small mb-1">Source VMID</label>
                    <input
                      type="number"
                      className="form-control form-control-sm"
                      value={form.source?.vmid ?? ''}
                      onChange={(e) =>
                        setSourceValue(
                          'vmid',
                          e.target.value === '' ? null : Number(e.target.value)
                        )
                      }
                      min="1"
                    />
                  </div>

                  <div className="col-lg-3">
                    <label className="form-label small mb-1">Target Storage</label>
                    <select
                      className="form-select form-select-sm"
                      value={form.source?.target?.storage_id || ''}
                      onChange={(e) => setSourceTargetValue('storage_id', e.target.value)}
                    >
                      <option value="">Vyber storage</option>

                      {diskStorages.map((storage) => (
                        <option key={storage.storage_id} value={storage.storage_id}>
                          {storage.storage || storage.storage_id}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="col-lg-2">
                    <div className="form-check mt-4">
                      <input
                        className="form-check-input"
                        type="checkbox"
                        id="clone_full"
                        checked={!!form.source?.target?.full}
                        onChange={(e) => setSourceTargetValue('full', e.target.checked)}
                      />
                      <label className="form-check-label small" htmlFor="clone_full">
                        Full clone
                      </label>
                    </div>
                  </div>
                </>
              )}

              {sourceType === 'template' && (
                <>
                  <div className="col-lg-4">
                    <label className="form-label small mb-1">Template</label>
                    <select
                      className="form-select form-select-sm"
                      value={form.source?.vmid ?? ''}
                      onChange={(e) =>
                        setSourceValue(
                          'vmid',
                          e.target.value === '' ? null : Number(e.target.value)
                        )
                      }
                    >
                      <option value="">Vyber template</option>

                      {availableTemplates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.name} ({template.id})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="col-lg-3">
                    <label className="form-label small mb-1">Target Storage</label>
                    <select
                      className="form-select form-select-sm"
                      value={form.source?.target?.storage_id || ''}
                      onChange={(e) => setSourceTargetValue('storage_id', e.target.value)}
                    >
                      <option value="">Vyber storage</option>

                      {diskStorages.map((storage) => (
                        <option key={storage.storage_id} value={storage.storage_id}>
                          {storage.storage || storage.storage_id}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="col-lg-2">
                    <div className="form-check mt-4">
                      <input
                        className="form-check-input"
                        type="checkbox"
                        id="template_full"
                        checked={!!form.source?.target?.full}
                        onChange={(e) => setSourceTargetValue('full', e.target.checked)}
                      />
                      <label className="form-check-label small" htmlFor="template_full">
                        Full clone
                      </label>
                    </div>
                  </div>

                  <div className="col-lg-3">
                    {templateConfigLoading && (
                      <div className="small text-muted mt-4">
                        Načítám konfiguraci templatu...
                      </div>
                    )}

                    {!templateConfigLoading && templateConfig && (
                      <div className="small text-success mt-4">
                        Konfigurace templatu načtena
                      </div>
                    )}
                  </div>

                  {templateConfig && (
                    <div className="col-12">
                      <div className="alert alert-secondary py-2 mt-2 mb-0" role="alert">
                        <div className="small">
                          <strong>Template config:</strong>{' '}
                          RAM {templateConfig.memory_mb ?? '-'} MB, CPU{' '}
                          {templateConfig.cpu?.cores ?? '-'} cores /{' '}
                          {templateConfig.cpu?.sockets ?? '-'} sockets, disks{' '}
                          {templateConfig.disks?.length ?? 0}, NICs{' '}
                          {templateConfig.networks?.length ?? 0}
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {sourceType !== 'backup' && (
              <>
                <hr className="my-2" />

                <h6 className="mb-2">Network</h6>

                <div className="row g-2 mb-2">
                  <div className="col-lg-6">
                    <label className="form-label small mb-1">Network</label>
                    <select
                      className="form-select form-select-sm"
                      value={form.networks[0]?.network_id || ''}
                      onChange={(e) => setPrimaryNetworkField('network_id', e.target.value)}
                    >
                      <option value="">Vyber network</option>

                      {availableNetworks.map((network, index) => (
                        <option key={getNetworkValue(network) || index} value={getNetworkValue(network)}>
                          {getNetworkLabel(network, index)}
                          {network.default ? ' (default)' : ''}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="col-lg-6">
                    <label className="form-label small mb-1">NIC model</label>
                    <select
                      className="form-select form-select-sm"
                      value={form.networks[0]?.model || ''}
                      onChange={(e) => setPrimaryNetworkField('model', e.target.value)}
                      disabled={!networkModels.length}
                    >
                      {networkModels.map((model) => (
                        <option key={model} value={model}>
                          {formatCapabilityLabel(model)}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <hr className="my-2" />

                <div className="d-flex justify-content-between align-items-center mb-2">
                  <h6 className="mb-0">Disks</h6>

                  <button
                    type="button"
                    className="btn btn-sm btn-outline-primary py-0 px-2"
                    onClick={handleAddDisk}
                  >
                    Přidat disk
                  </button>
                </div>

                <div className="d-flex flex-column gap-2 mb-2">
                  {form.disks.map((disk, index) => (
                    <div className="card" key={index}>
                      <div className="card-body p-2">
                        <div className="d-flex justify-content-between align-items-center mb-2">
                          <strong className="small">
                            Disk #{index + 1}{' '}
                            <span className="text-muted">({disk.slot})</span>
                          </strong>

                          <button
                            type="button"
                            className="btn btn-sm btn-outline-danger py-0 px-2"
                            onClick={() => handleRemoveDisk(index)}
                            disabled={form.disks.length === 1}
                          >
                            Odebrat
                          </button>
                        </div>

                        <div className="row g-2">
                          <div className="col-lg-3">
                            <label className="form-label small mb-1">Storage</label>
                            <select
                              className="form-select form-select-sm"
                              value={disk.storage_id}
                              onChange={(e) =>
                                handleDiskChange(index, 'storage_id', e.target.value)
                              }
                            >
                              <option value="">Vyber storage</option>

                              {diskStorages.map((storage) => (
                                <option key={storage.storage_id} value={storage.storage_id}>
                                  {storage.storage || storage.storage_id}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div className="col-lg-2">
                            <label className="form-label small mb-1">Size (GB)</label>
                            <input
                              type="number"
                              className="form-control form-control-sm"
                              value={disk.size_gb}
                              min="1"
                              onChange={(e) =>
                                handleDiskChange(index, 'size_gb', e.target.value)
                              }
                            />
                          </div>

                          <div className="col-lg-2">
                            <label className="form-label small mb-1">Bus</label>
                            <select
                              className="form-select form-select-sm"
                              value={disk.bus}
                              onChange={(e) =>
                                handleDiskChange(index, 'bus', e.target.value)
                              }
                              disabled={!diskBuses.length}
                            >
                              {diskBuses.map((bus) => (
                                <option key={bus} value={bus}>
                                  {formatCapabilityLabel(bus)}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div className="col-lg-3">
                            <label className="form-label small mb-1">Controller</label>
                            <select
                              className="form-select form-select-sm"
                              value={disk.controller_type}
                              onChange={(e) =>
                                handleDiskChange(index, 'controller_type', e.target.value)
                              }
                              disabled={!diskControllers.length}
                            >
                              {diskControllers.map((controller) => (
                                <option key={controller} value={controller}>
                                  {formatCapabilityLabel(controller)}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div className="col-lg-2">
                            <div className="form-check mt-4">
                              <input
                                className="form-check-input"
                                type="checkbox"
                                id={`disk-backup-${index}`}
                                checked={disk.backup !== false}
                                onChange={(e) =>
                                  handleDiskChange(index, 'backup', e.target.checked)
                                }
                              />

                              <label
                                className="form-check-label small"
                                htmlFor={`disk-backup-${index}`}
                              >
                                Backup
                              </label>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <hr className="my-2" />
              </>
            )}

            {sourceType !== 'backup' && (
              <details className="mb-2">
                <summary className="small fw-semibold">Advanced options</summary>

                <div className="row g-2 mt-1">
                  <div className="col-lg-4">
                    <label className="form-label small mb-1">Machine</label>
                    <select
                      className="form-select form-select-sm"
                      value={form.boot.machine}
                      onChange={(e) => setBootField('machine', e.target.value)}
                      disabled={!bootMachines.length}
                    >
                      {bootMachines.map((machine) => (
                        <option key={machine} value={machine}>
                          {formatCapabilityLabel(machine)}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="col-lg-4">
                    <label className="form-label small mb-1">BIOS / Firmware</label>
                    <select
                      className="form-select form-select-sm"
                      value={form.boot.firmware}
                      onChange={(e) => setBootField('firmware', e.target.value)}
                      disabled={!bootFirmwares.length}
                    >
                      {bootFirmwares.map((firmware) => (
                        <option key={firmware} value={firmware}>
                          {formatCapabilityLabel(firmware)}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="col-lg-4">
                    <label className="form-label small mb-1">Graphics</label>
                    <select
                      className="form-select form-select-sm"
                      value={form.options.graphics}
                      onChange={(e) => setOptionField('graphics', e.target.value)}
                      disabled={!graphicsModels.length}
                    >
                      {graphicsModels.map((graphics) => (
                        <option key={graphics} value={graphics}>
                          {formatCapabilityLabel(graphics)}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="row g-2 mt-2">
                  <div className="col-lg-4">
                    <div className="form-check">
                      <input
                        className="form-check-input"
                        type="checkbox"
                        id="start_after_create"
                        checked={form.options.start_after_create}
                        onChange={(e) =>
                          setOptionField('start_after_create', e.target.checked)
                        }
                      />
                      <label
                        className="form-check-label small"
                        htmlFor="start_after_create"
                      >
                        Start after create
                      </label>
                    </div>
                  </div>
                </div>
              </details>
            )}

            <div className="d-flex justify-content-end mt-2">
              <button
                type="submit"
                className="btn btn-success btn-sm"
                disabled={isSubmitDisabled}
              >
                submit
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default NodeCreateVm;