import React, { useEffect, useState } from 'react';
import { Container } from 'react-bootstrap';

import Spinner from '../Common/Spinner';
import MetricProgress from '../Common/MetricProgress';

import VmOverview from './VmOverview';
import VmSnapshots from './VmSnapshots';
import VmHwOptions from './VmHwOptions';
import VmConsole from './VmConsole';
import VmBackup from './VmBackups';
import VmLogs from './VmLogs';

import { fetchVmStatus, SetVmStatus } from '../../services/VmService';

import {
  VM_STATIC_FIELDS,
  VM_DYNAMIC_FIELDS,
  VM_ACTIONS
} from '../../utils/vm/constants';

import { formatUptime } from '../../utils/metrics/formatters';

function VmDetail({ selectedItem, onDeleteVm }) {
  const [vmDetails, setVmDetails] = useState(null);
  const [vmDetailsLoading, setVmDetailsLoading] = useState(false);
  const [vmActionLoading, setVmActionLoading] = useState(false);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showActionConfirm, setShowActionConfirm] = useState(false);

  const [activeView, setActiveView] = useState('overview');
  const [liveUptime, setLiveUptime] = useState(null);

  const [selectedAction, setSelectedAction] = useState('');
  const [pendingAction, setPendingAction] = useState(null);

  const hasSelectedVm = selectedItem?.type === 'vm';

  const canLoadVmData =
    hasSelectedVm &&
    selectedItem?.serverId != null &&
    selectedItem?.nodeId != null &&
    selectedItem?.id != null;

  const staticMetrics = vmDetails?.static || {};
  const dynamicMetrics = vmDetails?.dynamic || {};

  const currentStatus = staticMetrics.status || selectedItem?.status || 'unknown';
  const isRunning = currentStatus === 'running';

  const consoleProtocol =
    selectedItem?.platform?.toLowerCase() === 'esxi' ? 'webmks' : 'vnc';

  const memoryTotal = staticMetrics.memory_total || 0;
  const memoryUsed = dynamicMetrics.memory_used || 0;
  const diskTotal = Number(staticMetrics.disk_total) || 0;
  const diskUsed = Number(dynamicMetrics.disk_used) || 0;
  const cpuUsage = isRunning ? Number(dynamicMetrics.cpu_usage) * 100 || 0 : 0;

  function getActionLabel(action) {
    return VM_ACTIONS.find((item) => item.value === action)?.label || action;
  }

  async function loadVmStaticDetails(serverId, nodeId, vmId) {
    return fetchVmStatus(serverId, nodeId, vmId, VM_STATIC_FIELDS);
  }

  async function loadVmDynamicDetails(serverId, nodeId, vmId) {
    return fetchVmStatus(serverId, nodeId, vmId, VM_DYNAMIC_FIELDS);
  }

  async function loadVmDetails(serverId, nodeId, vmId, shouldLoadDynamic = true) {
    try {
      setVmDetailsLoading(true);

      const staticResult = await loadVmStaticDetails(serverId, nodeId, vmId);
      const dynamicResult = shouldLoadDynamic
        ? await loadVmDynamicDetails(serverId, nodeId, vmId)
        : {};

      setVmDetails({
        static: staticResult || {},
        dynamic: dynamicResult || {}
      });

      setLiveUptime(shouldLoadDynamic ? staticResult?.uptime ?? null : null);
    } catch (error) {
      console.error('Error loading VM details:', error);
      setVmDetails(null);
      setLiveUptime(null);
    } finally {
      setVmDetailsLoading(false);
    }
  }

  async function refreshVmDetails(nextStatus = currentStatus) {
    if (!canLoadVmData) return;

    await loadVmDetails(
      selectedItem.serverId,
      selectedItem.nodeId,
      selectedItem.id,
      nextStatus === 'running'
    );
  }

  async function handleDropVm() {
    if (!onDeleteVm || !hasSelectedVm || selectedItem?.serverId == null || selectedItem?.id == null) {
      console.error('Cannot delete VM, missing data:', selectedItem);
      return;
    }

    try {
      setVmActionLoading(true);
      await onDeleteVm(selectedItem);
    } catch (error) {
      console.error('Error deleting VM:', error);
    } finally {
      setVmActionLoading(false);
      setShowDeleteConfirm(false);
    }
  }

  async function handleVmAction(status) {
    const allowedStatuses = VM_ACTIONS.map((action) => action.value);

    try {
      setVmActionLoading(true);

      await SetVmStatus(
        selectedItem.serverId,
        selectedItem.nodeId,
        selectedItem.id,
        status
      );

      const nextStatus =
        status === 'start' || status === 'resume' || status === 'reboot'
          ? 'running'
          : status === 'stop' || status === 'shutdown'
            ? 'stopped'
            : status;

      await refreshVmDetails(nextStatus);
    } catch (error) {
      console.error(`Error executing VM action "${status}":`, error);
    } finally {
      setVmActionLoading(false);
    }
  }

  function handleSelectAction(event) {
    const action = event.target.value;
    setSelectedAction(action);

    if (!action) return;

    setPendingAction(action);
    setShowActionConfirm(true);
  }

  async function handleConfirmVmAction() {
    if (!pendingAction) return;

    await handleVmAction(pendingAction);

    setShowActionConfirm(false);
    setPendingAction(null);
    setSelectedAction('');
  }

  function handleCancelVmAction() {
    setShowActionConfirm(false);
    setPendingAction(null);
    setSelectedAction('');
  }

  useEffect(() => {
    if (!canLoadVmData) {
      setVmDetails(null);
      setLiveUptime(null);
      return;
    }

    const initialStatus = selectedItem?.status || 'unknown';

    loadVmDetails(
      selectedItem.serverId,
      selectedItem.nodeId,
      selectedItem.id,
      initialStatus === 'running'
    );
  }, [selectedItem, canLoadVmData]);

  useEffect(() => {
    if (!canLoadVmData || !isRunning || liveUptime == null) return;

    const intervalId = setInterval(() => {
      setLiveUptime((prev) => (prev == null ? prev : prev + 1));
    }, 1000);

    return () => clearInterval(intervalId);
  }, [canLoadVmData, isRunning, liveUptime]);

  useEffect(() => {
    if (!canLoadVmData || !isRunning) return;

    const intervalId = setInterval(async () => {
      try {
        const dynamicResult = await loadVmDynamicDetails(
          selectedItem.serverId,
          selectedItem.nodeId,
          selectedItem.id
        );

        if (!dynamicResult) return;

        setVmDetails((prev) =>
          prev
            ? {
                ...prev,
                dynamic: dynamicResult
              }
            : prev
        );
      } catch (error) {
        console.error('Error refreshing VM dynamic data:', error);
      }
    }, 5000);

    return () => clearInterval(intervalId);
  }, [selectedItem, canLoadVmData, isRunning]);

  if (!hasSelectedVm) {
    return (
      <div className="card h-100">
        <div className="card-body">Nebyla vybrána žádná VM.</div>
      </div>
    );
  }

  if (vmDetailsLoading) {
    return (
      <div className="card h-100">
        <div className="card-body d-flex justify-content-center align-items-center">
          <Spinner loading={true} />
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="card h-100 overflow-hidden">
        <div className="card-header bg-white d-flex justify-content-between align-items-center">
          <div>
            <h4 className="mb-0 d-flex align-items-center gap-2">
              {selectedItem.name || 'VM detail'}
              <span
                className={`rounded-circle ${isRunning ? 'bg-success' : 'bg-danger'}`}
                style={{ width: '10px', height: '10px', display: 'inline-block' }}
              />
            </h4>

            <small className="text-muted">
              <strong>Uptime:</strong> {formatUptime(liveUptime)}
              <span className="ms-2">
                <strong>VM ID:</strong> {selectedItem.id}
              </span>
              <span className="ms-2">
                <strong>Status:</strong> {currentStatus}
              </span>
            </small>
          </div>

          <button
            className="btn btn-outline-danger btn-sm"
            onClick={() => setShowDeleteConfirm(true)}
            disabled={vmActionLoading}
          >
            Drop VM
          </button>
        </div>

        <div className="card-body p-2 overflow-auto">
          <Container fluid className="p-0 d-flex flex-column h-100 overflow-y-hidden overflow-x-hidden">
            <div
              className="row d-flex row-cols-2 align-items-start flex-shrink-0"
              style={{ height: '200px' }}
            >
              <div className="col-6 pe-1 h-100">
                <div className="card p-3 h-100">
                  <div className="d-flex justify-content-between align-items-center mb-2">
                    <strong>CPU usage</strong>
                    <span className="text-muted small">
                      {isRunning
                        ? `${cpuUsage.toFixed(2)}% of ${staticMetrics.cpu_num || '-'} CPU(s)`
                        : `N/A of ${staticMetrics.cpu_num || '-'} CPU(s)`}
                    </span>
                  </div>

                  {isRunning ? (
                    <>
                      <div
                        className="progress"
                        role="progressbar"
                        aria-label="CPU usage"
                        aria-valuenow={cpuUsage}
                        aria-valuemin="0"
                        aria-valuemax="100"
                        style={{ height: '10px' }}
                      >
                        <div
                          className="progress-bar bg-info"
                          style={{
                            width: `${Math.min(100, Math.max(0, cpuUsage))}%`
                          }}
                        />
                      </div>

                      <div className="mt-3">
                        <MetricProgress label="RAM" total={memoryTotal} used={memoryUsed} />
                      </div>

                      <div className="mt-3">
                        <MetricProgress
                          label="Disk"
                          total={diskTotal}
                          used={diskUsed}
                          color="success"
                        />
                      </div>
                    </>
                  ) : (
                    <div className="text-muted small mt-3">
                      Runtime statistiky nejsou pro vypnutou VM dostupné.
                    </div>
                  )}
                </div>
              </div>

              <div className="col-6 ps-1 h-100">
                <div className="card p-3 h-100">
                  <div><strong>Status:</strong> {currentStatus}</div>
                  <div><strong>System name:</strong> {staticMetrics.sysname || '-'}</div>
                  <div><strong>OS type:</strong> {staticMetrics.ostype || '-'}</div>
                  <div><strong>CPU(s):</strong> {staticMetrics.cpu_num || '-'}</div>
                  <div><strong>Agent:</strong> {String(staticMetrics.agent ?? '-')}</div>
                </div>
              </div>
            </div>

            <div className="pt-2 pb-2">
              <div className="d-flex flex-wrap gap-2">
                <button className="btn btn-outline-success btn-sm" onClick={() => setActiveView('overview')}>
                  Overview
                </button>

                <button className="btn btn-outline-success btn-sm" onClick={() => setActiveView('hwoptions')}>
                  HW/Options
                </button>

                <button className="btn btn-outline-success btn-sm" onClick={() => setActiveView('snapshots')}>
                  Snapshots
                </button>

                <button className="btn btn-outline-success btn-sm" onClick={() => setActiveView('backup')}>
                  Backup
                </button>

                <button
                  className="btn btn-outline-dark btn-sm"
                  onClick={() => setActiveView('console')}
                  disabled={!isRunning}
                  title={!isRunning ? 'Console je dostupná jen pro běžící VM' : ''}
                >
                  Console
                </button>

                <button className="btn btn-outline-secondary btn-sm" onClick={() => setActiveView('logs')}>
                  Logs
                </button>

                <select
                  className="form-select form-select-sm"
                  style={{ width: '220px' }}
                  value={selectedAction}
                  onChange={handleSelectAction}
                  disabled={vmActionLoading}
                >
                  <option value="">Select action...</option>
                  {VM_ACTIONS.map((action) => (
                    <option key={action.value} value={action.value}>
                      {action.label}
                    </option>
                  ))}
                </select>

                {vmActionLoading && (
                  <span className="text-muted small">Provádím akci...</span>
                )}
              </div>
            </div>

            <div className="row d-flex flex-grow-1 position-relative overflow-hidden">
              {activeView === 'overview' && <VmOverview selectedItem={selectedItem} />}
              {activeView === 'snapshots' && <VmSnapshots selectedItem={selectedItem} />}
              {activeView === 'hwoptions' && <VmHwOptions selectedItem={selectedItem} />}

              {activeView === 'console' && isRunning && (
                <VmConsole selectedItem={selectedItem} preferredProtocol={consoleProtocol} />
              )}

              {activeView === 'console' && !isRunning && (
                <div className="col-12">
                  <div className="alert alert-secondary m-2 mb-0">
                    Console je dostupná pouze pro běžící VM.
                  </div>
                </div>
              )}

              {activeView === 'backup' && <VmBackup selectedItem={selectedItem} />}
              {activeView === 'logs' && <VmLogs selectedItem={selectedItem} limit={1000} />}
            </div>
          </Container>
        </div>
      </div>

      {showActionConfirm && (
        <div className="position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center"
          style={{ backgroundColor: 'rgba(0,0,0,0.35)', zIndex: 1050 }}>
          <div className="card shadow" style={{ width: '420px', maxWidth: '90%' }}>
            <div className="card-header bg-white">
              <strong>Confirm action</strong>
            </div>

            <div className="card-body">
              Are you sure you want to run action <strong>{getActionLabel(pendingAction)}</strong> on VM{' '}
              <strong>{selectedItem.name}</strong>?
            </div>

            <div className="card-footer bg-white d-flex justify-content-end gap-2">
              <button className="btn btn-outline-secondary btn-sm" onClick={handleCancelVmAction} disabled={vmActionLoading}>
                Cancel
              </button>

              <button className="btn btn-danger btn-sm" onClick={handleConfirmVmAction} disabled={vmActionLoading}>
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}

      {showDeleteConfirm && (
        <div className="position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center"
          style={{ backgroundColor: 'rgba(0,0,0,0.35)', zIndex: 1050 }}>
          <div className="card shadow" style={{ width: '420px', maxWidth: '90%' }}>
            <div className="card-header bg-white">
              <strong>Confirm delete</strong>
            </div>

            <div className="card-body">
              Are you sure you want to <strong>DELETE</strong> VM <strong>{selectedItem.name}</strong>?
              <div className="text-danger small mt-2">
                This action is irreversible.
              </div>
            </div>

            <div className="card-footer bg-white d-flex justify-content-end gap-2">
              <button className="btn btn-outline-secondary btn-sm" onClick={() => setShowDeleteConfirm(false)} disabled={vmActionLoading}>
                Cancel
              </button>

              <button className="btn btn-danger btn-sm" onClick={handleDropVm} disabled={vmActionLoading}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default VmDetail;