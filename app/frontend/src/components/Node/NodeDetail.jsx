import React, { useEffect, useState } from 'react';
import { Container } from 'react-bootstrap';
import Modal from '../Common/Modal';
import Storage from './NodeStorage';
import NodeOverview from './NodeOverview';
import NodeCreateVm from './NodeCreateVM';
import NodeLogs from './NodeLogs';
import Spinner from '../Common/Spinner';
import { fetchNodeStatus } from '../../services/NodeService';
import NodeConsole from './NodeConsole';

import MetricProgress from '../Common/MetricProgress';
import { formatUptime } from '../../utils/metrics/formatters';

import {
  NODE_STATIC_FIELDS,
  NODE_DYNAMIC_FIELDS
} from '../../utils/node/constants';

function NodeDetail({ selectedItem }) {
  const [nodeDetails, setNodeDetails] = useState(null);
  const [nodeDetailsLoading, setNodeDetailsLoading] = useState(false);
  const [activeView, setActiveView] = useState('overview');
  const [showCreateVmModal, setShowCreateVmModal] = useState(false);
  const [loadingView, setLoadingView] = useState(false);
  const [liveUptime, setLiveUptime] = useState(null);

  const isValidNode =
    selectedItem?.type === 'node' &&
    selectedItem?.serverId != null &&
    selectedItem?.id != null;
  
  const staticMetrics = nodeDetails?.static || {};
  const dynamicMetrics = nodeDetails?.dynamic || {};

  const memoryTotal = staticMetrics.memory_total || 0;
  const memoryUsed = dynamicMetrics.memory_used || 0;

  const swapTotal = staticMetrics.swap_total || 0;
  const swapUsed = dynamicMetrics.swap_used || 0;

  const diskTotal = staticMetrics.disk_total || 0;
  const diskFree = dynamicMetrics.disk_free || 0;
  const diskUsed = Math.max(0, diskTotal - diskFree);

  const cpuUsage = Number(dynamicMetrics.cpu_usage) * 100 || 0;
  
  const nodeTemplates = (selectedItem?.items || []).filter(
    (item) => item.type === 'template'
  );

  const handleOpenOverview = () => setActiveView('overview');
  const handleOpenStorage = () => setActiveView('storages');
  const handleOpenConsoleClick = () => setActiveView('console');
  const handleOpenLogsClick = () => setActiveView('logs');

  async function loadNodeStaticDetails(serverId, nodeId) {
    return await fetchNodeStatus(serverId, nodeId, NODE_STATIC_FIELDS);
  }

  async function loadNodeDynamicDetails(serverId, nodeId) {
    return await fetchNodeStatus(serverId, nodeId, NODE_DYNAMIC_FIELDS);
  }

  async function loadNodeDetails(serverId, nodeId) {
    try {
      setNodeDetailsLoading(true);

      const [staticResult, dynamicResult] = await Promise.all([
        loadNodeStaticDetails(serverId, nodeId),
        loadNodeDynamicDetails(serverId, nodeId),
      ]);

      setNodeDetails({
        static: staticResult,
        dynamic: dynamicResult,
      });

      setLiveUptime(staticResult?.uptime ?? null);
    } catch (error) {
      console.error('Error loading node details:', error);
      setNodeDetails(null);
      setLiveUptime(null);
    } finally {
      setNodeDetailsLoading(false);
    }
  }

  useEffect(() => {
    if (!isValidNode || liveUptime == null) return;

    const intervalId = setInterval(() => {
      setLiveUptime((prev) => (prev == null ? prev : prev + 1));
    }, 1000);

    return () => clearInterval(intervalId);
  }, [isValidNode, liveUptime]);

  useEffect(() => {
    if (!isValidNode) {
      setNodeDetails(null);
      setLiveUptime(null);
      return;
    }

    loadNodeDetails(selectedItem.serverId, selectedItem.id);
  }, [selectedItem, isValidNode]);

  useEffect(() => {
    if (!isValidNode) return;

    const intervalId = setInterval(async () => {
      try {
        const dynamicResult = await loadNodeDynamicDetails(
          selectedItem.serverId,
          selectedItem.id
        );

        if (!dynamicResult) return;

        setNodeDetails((prev) => {
          if (!prev) return prev;

          return {
            ...prev,
            dynamic: dynamicResult,
          };
        });
      } catch (error) {
        console.error('Error refreshing node dynamic data:', error);
      }
    }, 5000);

    return () => clearInterval(intervalId);
  }, [selectedItem, isValidNode]);

  if (!isValidNode) {
    return (
      <div className="card h-100">
        <div className="card-body">Nebyl vybrán žádný node.</div>
      </div>
    );
  }

  if (nodeDetailsLoading) {
    return (
      <div className="card h-100">
        <div className="card-body d-flex justify-content-center align-items-center">
          <Spinner loading={true} />
        </div>
      </div>
    );
  }

  return (
    <div className="card h-100 overflow-hidden">
      <div className="card-header bg-white d-flex justify-content-between align-items-center">
        <div>
          <h4 className="mb-0">{selectedItem.name || 'Node detail'}</h4>
          <small className="text-muted">
            <strong>Uptime:</strong> {formatUptime(liveUptime)}
          </small>
        </div>

        <div className="d-flex gap-2">
          <button
            className="btn btn-sm btn-success"
            onClick={() => setShowCreateVmModal(true)}
          >
            Create VM
          </button>
        </div>
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
                    {cpuUsage.toFixed(2)}% of {staticMetrics.cpu_num} CPU(s)
                  </span>
                </div>

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
                    style={{ width: `${Math.min(100, Math.max(0, cpuUsage))}%` }}
                  />
                </div>

                <div className="mt-1">
                  <MetricProgress
                    label="RAM"
                    total={memoryTotal}
                    used={memoryUsed}
                    color="primary"
                  />

                  {swapTotal > 0 && (
                    <MetricProgress
                      label="Swap"
                      total={swapTotal}
                      used={swapUsed}
                      color="warning"
                    />
                  )}
                </div>

                <div className="mt-1">
                  <MetricProgress
                    label="Disk usage"
                    total={diskTotal}
                    used={diskUsed}
                    color="success"
                  />
                </div>
              </div>
            </div>

            <div className="col-6 ps-1 h-100">
              <div className="card p-3 h-100">
                <div>
                  <strong>CPU(s):</strong> {staticMetrics.cpu_num || '-'} x{' '}
                  {staticMetrics.cpu_model || '-'} ({staticMetrics.cpu_sockets || '-'} Sockets)
                </div>
                <div>
                  <strong>OS:</strong> {staticMetrics.sysname || '-'}
                </div>
                <div>
                  <strong>Release:</strong> {staticMetrics.release || '-'}
                </div>
                <div>
                  <strong>Version:</strong> {staticMetrics.version || '-'}
                </div>
                {staticMetrics.boot_mode && (
                  <div>
                    <strong>Boot mode:</strong> {staticMetrics.boot_mode}
                  </div>
                )}
                {staticMetrics.pve_version && (
                  <div>
                    <strong>PVE version:</strong> {staticMetrics.pve_version}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="row">
            <div className="col-12">
              <div className="pt-2 pb-2">
                <div className="d-flex flex-wrap gap-2">
                  <button
                    className="btn btn-outline-success btn-sm"
                    onClick={handleOpenOverview}
                  >
                    Overview
                  </button>

                  <button
                    className="btn btn-outline-success btn-sm"
                    onClick={handleOpenStorage}
                  >
                    Storages
                  </button>

                  <button
                    className="btn btn-outline-dark btn-sm"
                    onClick={handleOpenConsoleClick}
                  >
                    Console
                  </button>

                  <button
                    className="btn btn-outline-secondary btn-sm"
                    onClick={handleOpenLogsClick}
                  >
                    Logs
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="row d-flex flex-grow-1 row-cols-2 position-relative overflow-hidden">
            <Spinner loading={loadingView} />

            {activeView === 'overview' && (
              <NodeOverview
                serverId={selectedItem.serverId}
                nodeId={selectedItem.id}
              />
            )}

            {activeView === 'storages' && (
              <Storage
                serverId={selectedItem.serverId}
                nodeId={selectedItem.id}
                onLoadingChange={setLoadingView}
              />
            )}

            {activeView === 'console' && (
              <NodeConsole
                serverId={selectedItem.serverId}
                nodeId={selectedItem.id}
              />
            )}

            {activeView === 'logs' && (
              <NodeLogs
                serverId={selectedItem.serverId}
                nodeId={selectedItem.id}
              />
            )}
          </div>

          {showCreateVmModal && (
            <Modal
              show={showCreateVmModal}
              title={`Create VM on ${selectedItem.name || 'node'}`}
              onClose={() => setShowCreateVmModal(false)}
            >
              <NodeCreateVm
                serverId={selectedItem.serverId}
                nodeId={selectedItem.id}
                platform={selectedItem.platform}
                templates={nodeTemplates}
                networks={selectedItem.networks || []}
                onCreated={() => {
                  setShowCreateVmModal(false);
                }}
                inModal={true}
              />
            </Modal>
          )}
        </Container>
      </div>
    </div>
  );
}

export default NodeDetail;