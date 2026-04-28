import React, { useEffect, useMemo, useState } from 'react';
import Spinner from '../Common/Spinner';

import {
  fetchVmConfiguration,
  updateVmConfiguration
} from '../../services/VmService';

import {
  fetchNodeStorage,
  fetchNodeStorageContent
} from '../../services/NodeService';

import {
  VM_GUEST_OPTIONS,
  VM_GRAPHICS_OPTIONS,
  VM_DISK_BUS_OPTIONS,
  VM_DISK_CONTROLLER_OPTIONS
} from '../../utils/vm/constants';

import {
  getDiskSlotPrefix,
  getBusFromSlot,
  getNextDiskSlot,
  storageHasContent
} from '../../utils/vm/createVmHelpers';

import { formatBytes } from '../../utils/metrics/formatters';

function VmHwOptions({ selectedItem }) {
  const [config, setConfig] = useState(null);
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const [storages, setStorages] = useState([]);
  const [storageLoading, setStorageLoading] = useState(false);
  const [isoFilesByStorage, setIsoFilesByStorage] = useState({});
  const [isoLoading, setIsoLoading] = useState(false);

  function formatBool(value) {
    return value ? 'Yes' : 'No';
  }

  const hasSelectedVm = selectedItem?.type === 'vm';
  
  const effectiveNodeId =
    selectedItem?.nodeId ?? selectedItem?.preferredNode?.id ?? null;

  const canLoadVmConfig =
    hasSelectedVm &&
    selectedItem?.serverId != null &&
    selectedItem?.id != null &&
    effectiveNodeId != null;

  async function loadVmConfig() {
    if (!canLoadVmConfig) {
      setConfig(null);
      setDraft(null);
      setIsEditing(false);
      return;
    }

    try {
      setLoading(true);
      setErrorMessage('');

      const result = await fetchVmConfiguration(
        selectedItem.serverId,
        effectiveNodeId,
        selectedItem.id
      );

      const vmConfig = result || null;
      const normalized = {
        ...vmConfig,
        disks: (vmConfig?.disks || []).map((disk) => ({
          ...disk,
          bus: disk.bus || getBusFromSlot(disk.slot),
        })),
        cdroms: vmConfig?.cdroms || [],
      };

      setConfig(normalized);
      setDraft(normalized);
      setIsEditing(false);
    } catch (error) {
      console.error('Error loading VM config:', error);
      setConfig(null);
      setDraft(null);
      setErrorMessage('Error while loading VM config.');
    } finally {
      setLoading(false);
    }
  }

  async function loadStorages() {
    if (selectedItem?.serverId == null || effectiveNodeId == null) {
      setStorages([]);
      return;
    }

    try {
      setStorageLoading(true);

      const result = await fetchNodeStorage(
        selectedItem.serverId,
        effectiveNodeId
      );

      const storageData = result || [];
      setStorages(Array.isArray(storageData) ? storageData : []);
    } catch (error) {
      console.error('Error loading storages:', error);
      setStorages([]);
    } finally {
      setStorageLoading(false);
    }
  }

  async function loadIsoFiles(storageId) {
    if (!storageId || isoFilesByStorage[storageId]) return;

    try {
      setIsoLoading(true);

      const result = await fetchNodeStorageContent(
        selectedItem.serverId,
        effectiveNodeId,
        storageId
      );

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
      setIsoFilesByStorage((prev) => ({ ...prev, [storageId]: [] }));
    } finally {
      setIsoLoading(false);
    }
  }

  useEffect(() => {
    loadVmConfig();
  }, [selectedItem, effectiveNodeId]);

  useEffect(() => {
    loadStorages();
  }, [selectedItem?.serverId, effectiveNodeId]);

  useEffect(() => {
    const cdroms = draft?.cdroms || [];
    cdroms.forEach((cdrom) => {
      if (cdrom?.storage_id) {
        loadIsoFiles(cdrom.storage_id);
      }
    });
  }, [draft?.cdroms]);

  function updateField(path, value) {
    setDraft((prev) => {
      if (!prev) return prev;

      const next = structuredClone(prev);
      let current = next;

      for (let i = 0; i < path.length - 1; i += 1) {
        const key = path[i];

        if (
          current[key] === undefined ||
          current[key] === null ||
          typeof current[key] !== 'object'
        ) {
          current[key] = {};
        }

        current = current[key];
      }

      current[path[path.length - 1]] = value;
      return next;
    });
  }

  function updateArrayItem(arrayName, index, field, value) {
    setDraft((prev) => {
      if (!prev) return prev;

      const next = structuredClone(prev);

      if (!Array.isArray(next[arrayName])) {
        next[arrayName] = [];
      }

      if (!next[arrayName][index]) {
        next[arrayName][index] = {};
      }

      next[arrayName][index][field] = value;
      return next;
    });
  }

  function handleDiskChange(index, field, value) {
    setDraft((prev) => {
      if (!prev) return prev;

      const next = structuredClone(prev);
      const currentDisk = next.disks?.[index];
      if (!currentDisk) return prev;

      const oldSlot = currentDisk.slot;

      currentDisk[field] =
        field === 'size_gb'
          ? value === ''
            ? ''
            : Number(value)
          : value;

      if (field === 'bus') {
        currentDisk.slot = getNextDiskSlot(next.disks, value, index);
      }

      if ((field === 'slot' || field === 'bus') && next.boot?.order?.length) {
        next.boot.order = next.boot.order.map((item) =>
          item === oldSlot ? currentDisk.slot : item
        );
      }

      return next;
    });
  }

  function addDisk() {
    setDraft((prev) => {
      if (!prev) return prev;

      const next = structuredClone(prev);
      if (!Array.isArray(next.disks)) {
        next.disks = [];
      }

      const bus = 'scsi';
      const slot = getNextDiskSlot(next.disks, bus);

      next.disks.push({
        slot,
        storage_id: '',
        volume: '',
        size_gb: 10,
        bus,
        controller_type: 'virtio-scsi-single',
        backup: true,
      });

      return next;
    });
  }

  function removeDisk(indexToRemove) {
    setDraft((prev) => {
      if (!prev) return prev;

      const next = structuredClone(prev);
      const removedSlot = next.disks?.[indexToRemove]?.slot;

      next.disks = (next.disks || []).filter(
        (_, index) => index !== indexToRemove
      );

      if (removedSlot && Array.isArray(next.boot?.order)) {
        next.boot.order = next.boot.order.filter((item) => item !== removedSlot);
      }

      return next;
    });
  }

  function addCdrom() {
    setDraft((prev) => {
      if (!prev) return prev;

      const next = structuredClone(prev);

      if (!Array.isArray(next.cdroms)) {
        next.cdroms = [];
      }

      const usedSlots = next.cdroms
        .map((item) => item?.slot)
        .filter(Boolean);

      const defaultSlot = usedSlots.includes('ide2') ? 'ide3' : 'ide2';

      next.cdroms.push({
        slot: defaultSlot,
        storage_id: '',
        volume: '',
      });

      return next;
    });
  }

  function removeCdrom(indexToRemove) {
    setDraft((prev) => {
      if (!prev) return prev;

      const next = structuredClone(prev);
      const removedSlot = next.cdroms?.[indexToRemove]?.slot;

      next.cdroms = (next.cdroms || []).filter(
        (_, index) => index !== indexToRemove
      );

      if (removedSlot && Array.isArray(next.boot?.order)) {
        next.boot.order = next.boot.order.filter((item) => item !== removedSlot);
      }

      return next;
    });
  }

  function moveBootOrderItem(index, direction) {
    setDraft((prev) => {
      if (!prev) return prev;

      const currentOrder = Array.isArray(prev.boot?.order)
        ? [...prev.boot.order]
        : [];
      const targetIndex = index + direction;

      if (targetIndex < 0 || targetIndex >= currentOrder.length) {
        return prev;
      }

      [currentOrder[index], currentOrder[targetIndex]] = [
        currentOrder[targetIndex],
        currentOrder[index],
      ];

      const next = structuredClone(prev);
      if (!next.boot) next.boot = {};
      next.boot.order = currentOrder;
      return next;
    });
  }

  function removeBootOrderItem(indexToRemove) {
    setDraft((prev) => {
      if (!prev) return prev;

      const next = structuredClone(prev);
      if (!Array.isArray(next.boot?.order)) {
        if (!next.boot) next.boot = {};
        next.boot.order = [];
        return next;
      }

      next.boot.order = next.boot.order.filter(
        (_, index) => index !== indexToRemove
      );
      return next;
    });
  }

  function addBootOrderItem(value) {
    if (!value) return;

    setDraft((prev) => {
      if (!prev) return prev;

      const next = structuredClone(prev);
      if (!next.boot) next.boot = {};
      if (!Array.isArray(next.boot.order)) {
        next.boot.order = [];
      }

      if (!next.boot.order.includes(value)) {
        next.boot.order.push(value);
      }

      return next;
    });
  }

  function cancelEdit() {
    setDraft(config ? structuredClone(config) : null);
    setIsEditing(false);
    setErrorMessage('');
  }

  function buildUpdatePayload(edited) {
    return {
      ...edited,
      disks: (edited.disks || []).map((disk) => ({
        ...disk,
        size_gb:
          disk.size_gb === '' || disk.size_gb == null
            ? null
            : Number(disk.size_gb),
      })),
    };
  }

  async function handleSave() {
    if (!draft || !config || !canLoadVmConfig) return;

    try {
      setSaving(true);
      setErrorMessage('');

      const payload = buildUpdatePayload(draft);

      await updateVmConfiguration(
        selectedItem.serverId,
        effectiveNodeId,
        selectedItem.id,
        payload
      );

      setConfig(structuredClone(draft));
      setIsEditing(false);
    } catch (error) {
      console.error('Error saving VM config:', error);
      setErrorMessage('Error while saving VM config.');
    } finally {
      setSaving(false);
    }
  }

  const data = draft || {};
  const cpu = data.cpu || {};
  const disks = data.disks || [];
  const cdroms = data.cdroms || [];
  const networks = data.networks || [];
  const boot = data.boot || {};
  const options = data.options || {};

  const hasChanges = useMemo(() => {
    return JSON.stringify(config) !== JSON.stringify(draft);
  }, [config, draft]);

  const diskStorages = useMemo(() => {
    return storages.filter(
      (storage) =>
        storageHasContent(storage, 'images') ||
        storageHasContent(storage, 'rootdir')
    );
  }, [storages]);

  const isoCapableStorages = useMemo(() => {
    return storages.filter((storage) => storageHasContent(storage, 'iso'));
  }, [storages]);

  const bootOrderOptions = useMemo(() => {
    const diskItems = disks
      .map((disk) => disk?.slot)
      .filter(Boolean)
      .map((slot) => ({ value: slot, label: slot }));

    const cdromItems = cdroms
      .map((cdrom) => cdrom?.slot)
      .filter(Boolean)
      .map((slot) => ({ value: slot, label: `${slot} (CD/DVD)` }));

    return [...diskItems, ...cdromItems];
  }, [disks, cdroms]);

  if (!hasSelectedVm) {
    return (
      <div className="col-12 h-100">
        <div className="card h-100">
          <div className="card-body d-flex align-items-center text-muted">
            Nebyla vybrána žádná VM.
          </div>
        </div>
      </div>
    );
  }

  function renderTextInput(value, onChange, disabled = false, type = 'text') {
    if (!isEditing) return value ?? '-';

    return (
      <input
        type={type}
        className="form-control form-control-sm"
        value={value ?? ''}
        onChange={(e) =>
          onChange(
            type === 'number'
              ? e.target.value === ''
                ? ''
                : Number(e.target.value)
              : e.target.value
          )
        }
        disabled={disabled}
      />
    );
  }

  function renderCheckbox(value, onChange) {
    if (!isEditing) return formatBool(value);

    return (
      <input
        type="checkbox"
        className="form-check-input"
        checked={!!value}
        onChange={(e) => onChange(e.target.checked)}
      />
    );
  }

  return (
    <div className="col-12 h-100">
      <div className="card h-100">
        <div className="card-header bg-white d-flex justify-content-between align-items-center">
          <strong>Hardware / Options</strong>

          <div className="d-flex gap-2">
            <button
              className="btn btn-outline-secondary btn-sm"
              onClick={loadVmConfig}
              disabled={loading || saving}
            >
              Refresh
            </button>

            {!isEditing ? (
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setIsEditing(true)}
                disabled={!draft || loading || saving}
              >
                Edit
              </button>
            ) : (
              <>
                <button
                  className="btn btn-outline-secondary btn-sm"
                  onClick={cancelEdit}
                  disabled={saving}
                >
                  Cancel
                </button>
                <button
                  className="btn btn-success btn-sm"
                  onClick={handleSave}
                  disabled={saving || !hasChanges}
                >
                  Save
                </button>
              </>
            )}
          </div>
        </div>

        <div
          className="card-body position-relative p-2 d-flex flex-column"
          style={{ minHeight: 0, overflow: 'hidden' }}
        >
          <Spinner loading={loading || saving || storageLoading || isoLoading} />

          {errorMessage && (
            <div className="alert alert-danger py-2" role="alert">
              {errorMessage}
            </div>
          )}

          {!draft && !loading ? (
            <div className="text-muted">No VM config available.</div>
          ) : (
            <div
              className="row g-3 flex-grow-1 h-100 align-items-stretch"
              style={{ minHeight: 0 }}
            >
              <div
                className="col-lg-4 d-flex flex-column h-100"
                style={{ minHeight: 0 }}
              >
                <div
                  className="card w-100 h-100 d-flex flex-column"
                  style={{ minHeight: 0 }}
                >
                  <div className="card-header py-2 bg-light">Basic info</div>
                  <div
                    className="card-body p-0 flex-grow-1"
                    style={{ minHeight: 0, overflowY: 'auto' }}
                  >
                    <table className="table table-sm table-bordered align-middle mb-0">
                      <tbody>
                        <tr>
                          <th style={{ width: 140 }}>VM ID</th>
                          <td>{data?.vmid ?? '-'}</td>
                        </tr>
                        <tr>
                          <th>Name</th>
                          <td>
                            {renderTextInput(data?.name, (value) =>
                              updateField(['name'], value)
                            )}
                          </td>
                        </tr>
                        <tr>
                          <th>Guest</th>
                          <td>
                            {!isEditing ? (
                              data?.guest || '-'
                            ) : (
                              <select
                                className="form-select form-select-sm"
                                value={data?.guest || 'other64'}
                                onChange={(e) =>
                                  updateField(['guest'], e.target.value)
                                }
                              >
                                {VM_GUEST_OPTIONS.map((option) => (
                                  <option
                                    key={option.value}
                                    value={option.value}
                                  >
                                    {option.label}
                                  </option>
                                ))}
                              </select>
                            )}
                          </td>
                        </tr>
                        <tr>
                          <th>Memory</th>
                          <td>
                            {isEditing ? (
                              <input
                                type="number"
                                className="form-control form-control-sm"
                                value={data?.memory_mb ?? ''}
                                onChange={(e) =>
                                  updateField(
                                    ['memory_mb'],
                                    e.target.value === ''
                                      ? ''
                                      : Number(e.target.value)
                                  )
                                }
                              />
                            ) : (
                              formatBytes(Number(data?.memory_mb) * 1024 ** 2, 2, 'auto')
                            )}
                          </td>
                        </tr>
                        <tr>
                          <th style={{ width: 140 }}>Cores</th>
                          <td>
                            {renderTextInput(
                              cpu.cores,
                              (value) => updateField(['cpu', 'cores'], value),
                              false,
                              'number'
                            )}
                          </td>
                        </tr>
                        <tr>
                          <th>Sockets</th>
                          <td>
                            {renderTextInput(
                              cpu.sockets,
                              (value) =>
                                updateField(['cpu', 'sockets'], value),
                              false,
                              'number'
                            )}
                          </td>
                        </tr>
                        <tr>
                          <th>Type</th>
                          <td>
                            {renderTextInput(cpu.type, (value) =>
                              updateField(['cpu', 'type'], value)
                            )}
                          </td>
                        </tr>
                        <tr>
                          <th>Order</th>
                          <td>
                            {!isEditing ? (
                              Array.isArray(boot.order) && boot.order.length > 0 ? (
                                <div className="d-flex flex-column gap-1">
                                  {boot.order.map((item, index) => (
                                    <div key={`${item}-${index}`}>
                                      {index + 1}. {item}
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                '-'
                              )
                            ) : (
                              <div className="d-flex flex-column gap-2">
                                {Array.isArray(boot.order) && boot.order.length > 0 ? (
                                  boot.order.map((item, index) => (
                                    <div
                                      key={`${item}-${index}`}
                                      className="d-flex justify-content-between align-items-center border rounded px-2 py-1"
                                    >
                                      <span className="small">
                                        {index + 1}. {item}
                                      </span>

                                      <div className="btn-group btn-group-sm">
                                        <button
                                          type="button"
                                          className="btn btn-outline-secondary"
                                          disabled={index === 0}
                                          onClick={() => moveBootOrderItem(index, -1)}
                                          title="Posunout nahoru"
                                        >
                                          ↑
                                        </button>
                                        <button
                                          type="button"
                                          className="btn btn-outline-secondary"
                                          disabled={index === boot.order.length - 1}
                                          onClick={() => moveBootOrderItem(index, 1)}
                                          title="Posunout dolů"
                                        >
                                          ↓
                                        </button>
                                        <button
                                          type="button"
                                          className="btn btn-outline-danger"
                                          onClick={() => removeBootOrderItem(index)}
                                          title="Odebrat z boot order"
                                        >
                                          ×
                                        </button>
                                      </div>
                                    </div>
                                  ))
                                ) : (
                                  <div className="text-muted small">No boot devices selected.</div>
                                )}

                                <select
                                  className="form-select form-select-sm"
                                  defaultValue=""
                                  onChange={(e) => {
                                    addBootOrderItem(e.target.value);
                                    e.target.value = '';
                                  }}
                                >
                                  <option value="">Přidat zařízení do boot order</option>
                                  {bootOrderOptions
                                    .filter(
                                      (option) =>
                                        !Array.isArray(boot.order) ||
                                        !boot.order.includes(option.value)
                                    )
                                    .map((item) => (
                                      <option key={item.value} value={item.value}>
                                        {item.label}
                                      </option>
                                    ))}
                                </select>
                              </div>
                            )}
                          </td>
                        </tr>
                        <tr>
                          <th>Firmware</th>
                          <td>
                            {renderTextInput(boot.firmware, (value) =>
                              updateField(['boot', 'firmware'], value)
                            )}
                          </td>
                        </tr>
                        <tr>
                          <th>Machine</th>
                          <td>
                            {renderTextInput(boot.machine, (value) =>
                              updateField(['boot', 'machine'], value)
                            )}
                          </td>
                        </tr>
                        <tr>
                          <th>Autostart</th>
                          <td>
                            {renderCheckbox(options.autostart, (value) =>
                              updateField(['options', 'autostart'], value)
                            )}
                          </td>
                        </tr>
                        <tr>
                          <th>Graphics</th>
                          <td>
                            {!isEditing ? (
                              options.graphics || '-'
                            ) : (
                              <select
                                className="form-select form-select-sm"
                                value={options.graphics || 'default'}
                                onChange={(e) =>
                                  updateField(
                                    ['options', 'graphics'],
                                    e.target.value
                                  )
                                }
                              >
                                {VM_GRAPHICS_OPTIONS.map((option) => (
                                  <option
                                    key={option.value}
                                    value={option.value}
                                  >
                                    {option.label}
                                  </option>
                                ))}
                              </select>
                            )}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <div
                className="col-lg-8 d-flex flex-column h-100"
                style={{ minHeight: 0 }}
              >
                <div
                  className="card mb-3 d-flex flex-column"
                  style={{ minHeight: 0, flex: '1 1 0' }}
                >
                  <div className="card-header py-2 bg-light d-flex justify-content-between align-items-center">
                    <span>Disks</span>
                    {isEditing && (
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-primary"
                        onClick={addDisk}
                      >
                        Add disk
                      </button>
                    )}
                  </div>
                  <div
                    className="card-body p-0 flex-grow-1"
                    style={{ minHeight: 0, overflowY: 'auto' }}
                  >
                    <div className="table-responsive h-100">
                      <table className="table table-sm table-bordered align-middle mb-0">
                        <thead>
                          <tr>
                            <th>Slot</th>
                            <th>Bus</th>
                            <th>Storage</th>
                            <th>Volume</th>
                            <th>Size</th>
                            <th>Controller</th>
                            {isEditing && (
                              <th style={{ width: 90 }}>Actions</th>
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {disks.length === 0 ? (
                            <tr>
                              <td
                                colSpan={isEditing ? 7 : 6}
                                className="text-muted text-center"
                              >
                                No disks configured.
                              </td>
                            </tr>
                          ) : (
                            disks.map((disk, index) => {
                              const bus = disk.bus || getBusFromSlot(disk.slot);
                              const prefix = getDiskSlotPrefix(bus);

                              return (
                                <tr key={disk.slot || index}>
                                  <td>
                                    {!isEditing ? (
                                      disk.slot || '-'
                                    ) : (
                                      <select
                                        className="form-select form-select-sm"
                                        value={disk.slot ?? ''}
                                        onChange={(e) =>
                                          handleDiskChange(
                                            index,
                                            'slot',
                                            e.target.value
                                          )
                                        }
                                      >
                                        <option value="">Vyber slot</option>
                                        {Array.from({ length: 8 }).map(
                                          (_, slotIndex) => {
                                            const slotValue = `${prefix}${slotIndex}`;
                                            return (
                                              <option
                                                key={slotValue}
                                                value={slotValue}
                                              >
                                                {slotValue}
                                              </option>
                                            );
                                          }
                                        )}
                                      </select>
                                    )}
                                  </td>

                                  <td>
                                    {!isEditing ? (
                                      bus
                                    ) : (
                                      <select
                                        className="form-select form-select-sm"
                                        value={bus}
                                        onChange={(e) =>
                                          handleDiskChange(
                                            index,
                                            'bus',
                                            e.target.value
                                          )
                                        }
                                      >
                                        {VM_DISK_BUS_OPTIONS.map((option) => (
                                          <option
                                            key={option.value}
                                            value={option.value}
                                          >
                                            {option.label}
                                          </option>
                                        ))}
                                      </select>
                                    )}
                                  </td>

                                  <td>
                                    {!isEditing ? (
                                      disk.storage || '-'
                                    ) : (
                                      <select
                                        className="form-select form-select-sm"
                                        value={disk.storage_id ?? ''}
                                        onChange={(e) =>
                                          handleDiskChange(
                                            index,
                                            'storage_id',
                                            e.target.value
                                          )
                                        }
                                      >
                                        <option value="">Vyber storage</option>
                                        {diskStorages.map((storage) => (
                                          <option
                                            key={storage.storage_id}
                                            value={storage.storage_id}
                                          >
                                            {storage.storage ||
                                              storage.storage_id}
                                          </option>
                                        ))}
                                      </select>
                                    )}
                                  </td>

                                  <td>
                                    {isEditing ? (
                                      <input
                                        className="form-control form-control-sm"
                                        value={disk.volume ?? ''}
                                        onChange={(e) =>
                                          handleDiskChange(
                                            index,
                                            'volume',
                                            e.target.value
                                          )
                                        }
                                      />
                                    ) : (
                                      disk.volume || '-'
                                    )}
                                  </td>

                                  <td>
                                    {isEditing ? (
                                      <input
                                        type="number"
                                        min="1"
                                        className="form-control form-control-sm"
                                        value={disk.size_gb ?? ''}
                                        onChange={(e) =>
                                          handleDiskChange(
                                            index,
                                            'size_gb',
                                            e.target.value
                                          )
                                        }
                                      />
                                    ) : (
                                      formatBytes(Number(disk.size_gb) * 1024 ** 3, 2, 'auto')
                                    )}
                                  </td>

                                  <td>
                                    {!isEditing ? (
                                      disk.controller_type || '-'
                                    ) : (
                                      <select
                                        className="form-select form-select-sm"
                                        value={
                                          disk.controller_type ??
                                          'virtio-scsi-single'
                                        }
                                        onChange={(e) =>
                                          handleDiskChange(
                                            index,
                                            'controller_type',
                                            e.target.value
                                          )
                                        }
                                      >
                                        {VM_DISK_CONTROLLER_OPTIONS.map(
                                          (option) => (
                                            <option
                                              key={option.value}
                                              value={option.value}
                                            >
                                              {option.label}
                                            </option>
                                          )
                                        )}
                                      </select>
                                    )}
                                  </td>

                                  {isEditing && (
                                    <td>
                                      <button
                                        type="button"
                                        className="btn btn-sm btn-outline-danger"
                                        onClick={() => removeDisk(index)}
                                      >
                                        Delete
                                      </button>
                                    </td>
                                  )}
                                </tr>
                              );
                            })
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                <div
                  className="card mb-3 d-flex flex-column"
                  style={{ minHeight: 0, flex: '1 1 0' }}
                >
                  <div className="card-header py-2 bg-light">Network</div>
                  <div
                    className="card-body p-0 flex-grow-1"
                    style={{ minHeight: 0, overflowY: 'auto' }}
                  >
                    <div className="table-responsive h-100">
                      <table className="table table-sm table-bordered align-middle mb-0">
                        <thead>
                          <tr>
                            <th>Slot</th>
                            <th>Bridge</th>
                            <th>Model</th>
                            <th>MAC</th>
                            <th>Connected</th>
                          </tr>
                        </thead>
                        <tbody>
                          {networks.length === 0 ? (
                            <tr>
                              <td
                                colSpan="5"
                                className="text-muted text-center"
                              >
                                No network devices configured.
                              </td>
                            </tr>
                          ) : (
                            networks.map((net, index) => (
                              <tr key={net.slot || index}>
                                <td>{net.slot || '-'}</td>
                                <td>
                                  {isEditing ? (
                                    <input
                                      className="form-control form-control-sm"
                                      value={net.network_id ?? ''}
                                      onChange={(e) =>
                                        updateArrayItem(
                                          'networks',
                                          index,
                                          'network_id',
                                          e.target.value
                                        )
                                      }
                                    />
                                  ) : (
                                    net.network_id || '-'
                                  )}
                                </td>
                                <td>
                                  {isEditing ? (
                                    <input
                                      className="form-control form-control-sm"
                                      value={net.model ?? ''}
                                      onChange={(e) =>
                                        updateArrayItem(
                                          'networks',
                                          index,
                                          'model',
                                          e.target.value
                                        )
                                      }
                                    />
                                  ) : (
                                    net.model || '-'
                                  )}
                                </td>
                                <td>
                                  {isEditing ? (
                                    <input
                                      className="form-control form-control-sm"
                                      value={net.mac ?? ''}
                                      onChange={(e) =>
                                        updateArrayItem(
                                          'networks',
                                          index,
                                          'mac',
                                          e.target.value
                                        )
                                      }
                                    />
                                  ) : (
                                    net.mac || '-'
                                  )}
                                </td>
                                <td>
                                  {isEditing ? (
                                    <input
                                      type="checkbox"
                                      className="form-check-input"
                                      checked={!!net.connected}
                                      onChange={(e) =>
                                        updateArrayItem(
                                          'networks',
                                          index,
                                          'connected',
                                          e.target.checked
                                        )
                                      }
                                    />
                                  ) : (
                                    formatBool(net.connected)
                                  )}
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                <div
                  className="card d-flex flex-column"
                  style={{ minHeight: 0, flex: '1 1 0' }}
                >
                  <div className="card-header py-2 bg-light d-flex justify-content-between align-items-center">
                    <span>CD/DVD</span>
                    {isEditing && (
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-primary"
                        onClick={addCdrom}
                      >
                        Add ISO
                      </button>
                    )}
                  </div>
                  <div
                    className="card-body p-0 flex-grow-1"
                    style={{ minHeight: 0, overflowY: 'auto' }}
                  >
                    <div className="table-responsive h-100">
                      <table className="table table-sm table-bordered align-middle mb-0">
                        <thead>
                          <tr>
                            <th>Slot</th>
                            <th>Storage</th>
                            <th>ISO</th>
                            {isEditing && (
                              <th style={{ width: 90 }}>Actions</th>
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {cdroms.length === 0 ? (
                            <tr>
                              <td
                                colSpan={isEditing ? 4 : 3}
                                className="text-muted text-center"
                              >
                                No CD/DVD devices configured.
                              </td>
                            </tr>
                          ) : (
                            cdroms.map((cdrom, index) => {
                              const availableIsoFiles =
                                isoFilesByStorage[cdrom.storage_id] || [];

                              return (
                                <tr key={cdrom.slot || index}>
                                  <td>
                                    {!isEditing ? (
                                      cdrom.slot || '-'
                                    ) : (
                                      <select
                                        className="form-select form-select-sm"
                                        value={cdrom.slot ?? ''}
                                        onChange={(e) =>
                                          updateArrayItem(
                                            'cdroms',
                                            index,
                                            'slot',
                                            e.target.value
                                          )
                                        }
                                      >
                                        <option value="ide2">ide2</option>
                                        <option value="ide3">ide3</option>
                                        <option value="sata0">sata0</option>
                                        <option value="sata1">sata1</option>
                                      </select>
                                    )}
                                  </td>

                                  <td>
                                    {!isEditing ? (
                                      cdrom.storage || '-'
                                    ) : (
                                      <select
                                        className="form-select form-select-sm"
                                        value={cdrom.storage_id ?? ''}
                                        onChange={(e) =>
                                          updateArrayItem(
                                            'cdroms',
                                            index,
                                            'storage_id',
                                            e.target.value
                                          )
                                        }
                                      >
                                        <option value="">Vyber storage</option>
                                        {isoCapableStorages.map((storage) => (
                                          <option
                                            key={storage.storage_id}
                                            value={storage.storage_id}
                                          >
                                            {storage.storage ||
                                              storage.storage_id}
                                          </option>
                                        ))}
                                      </select>
                                    )}
                                  </td>

                                  <td>
                                    {!isEditing ? (
                                      cdrom.volume || '-'
                                    ) : (
                                      <select
                                        className="form-select form-select-sm"
                                        value={cdrom.volume ?? ''}
                                        onChange={(e) =>
                                          updateArrayItem(
                                            'cdroms',
                                            index,
                                            'volume',
                                            e.target.value
                                          )
                                        }
                                        disabled={!cdrom.storage_id}
                                      >
                                        <option value="">
                                          {isoLoading
                                            ? 'Načítám ISO...'
                                            : 'Vyber ISO'}
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
                                    )}
                                  </td>

                                  {isEditing && (
                                    <td>
                                      <button
                                        type="button"
                                        className="btn btn-sm btn-outline-danger"
                                        onClick={() => removeCdrom(index)}
                                      >
                                        Delete
                                      </button>
                                    </td>
                                  )}
                                </tr>
                              );
                            })
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default VmHwOptions;