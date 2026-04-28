import React, { useMemo, useState } from 'react';
import ServerAutomation from './ServerAutomation';

function ServerDetail({ selectedItem, onRefreshServers }) {
  const [activeTab, setActiveTab] = useState('overview');

  const serverStatus = selectedItem?.connected ? 'Connected' : 'Disconnected';

  const summary = useMemo(() => {
  const clusters = selectedItem?.clusters || [];
  const nodes = clusters.flatMap((cluster) => cluster.nodes || []);

  const vmCount = nodes.reduce((count, node) => {
        return count + (node.items || []).filter((item) => item.type === 'vm').length;
    }, 0);

    const templateCountFromNodes = nodes.reduce((count, node) => {
        return count + (node.items || []).filter((item) => item.type === 'template').length;
    }, 0);

    const templateCountFromClusters = clusters.reduce((count, cluster) => {
        return count + (cluster.templates || []).length;
    }, 0);

    const stoppedVmCount = clusters.reduce((count, cluster) => {
        return count + (cluster.orphanVms || []).length;
    }, 0);

    return {
        clusterCount: clusters.length,
        nodeCount: nodes.length,
        vmCount,
        templateCount: templateCountFromNodes + templateCountFromClusters,
        stoppedVmCount
    };
    }, [selectedItem]);

  if (!selectedItem) {
    return (
      <div className="flex-grow-1 ps-3">
        <div className="card h-100">
          <div className="card-body text-center text-muted">
            Vyber server.
          </div>
        </div>
      </div>
    );
  }

  const clusters = selectedItem.clusters || [];

  return (
    <div className="flex-grow-1 ps-3">
      <div className="card h-100">
        {/* HEADER */}
        <div className="card-header d-flex justify-content-between align-items-center">
          <div>
            <strong>{selectedItem.name}</strong>
            <div className="small text-muted">
              {selectedItem.host || '-'} · {selectedItem.platform || '-'}
            </div>
          </div>

          <span className={`badge ${selectedItem.connected ? 'bg-success' : 'bg-secondary'}`}>
            {serverStatus}
          </span>
        </div>

        {/* TABS */}
        <div className="card-header p-0">
         <div className="p-2">
            <div>
                <button
                type="button"
                className={`btn ${
                    activeTab === 'overview' ? 'btn-primary' : 'btn-outline-primary'
                }`}
                onClick={() => setActiveTab('overview')}
                >
                Overview
                </button>

                <button
                type="button"
                className={`btn ms-1 ${
                    activeTab === 'automation' ? 'btn-primary' : 'btn-outline-primary'
                }`}
                onClick={() => setActiveTab('automation')}
                >
                Automation
                </button>
            </div>
            </div>
        </div>

        {/* BODY */}
        <div className="card-body overflow-auto">
          {activeTab === 'overview' && (
            <div className="d-flex flex-column gap-3">
              
              {/* SUMMARY */}
              <div className="row">
                <div className="col-md-3">
                  <div className="card">
                    <div className="card-body text-center">
                      <div className="small text-muted">Clusters</div>
                      <div>{summary.clusterCount}</div>
                    </div>
                  </div>
                </div>

                <div className="col-md-3">
                  <div className="card">
                    <div className="card-body text-center">
                      <div className="small text-muted">Nodes</div>
                      <div>{summary.nodeCount}</div>
                    </div>
                  </div>
                </div>

                <div className="col-md-3">
                  <div className="card">
                    <div className="card-body text-center">
                      <div className="small text-muted">VMs</div>
                      <div>{summary.vmCount}</div>
                    </div>
                  </div>
                </div>

                <div className="col-md-3">
                  <div className="card">
                    <div className="card-body text-center">
                      <div className="small text-muted">Templates</div>
                      <div>{summary.templateCount}</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* SERVER INFO */}
              <div className="card">
                <div className="card-header">Server info</div>
                <div className="card-body">
                  <div><strong>Name:</strong> {selectedItem.name}</div>
                  <div><strong>Host:</strong> {selectedItem.host || '-'}</div>
                  <div><strong>Platform:</strong> {selectedItem.platform || '-'}</div>
                  <div><strong>Username:</strong> {selectedItem.username || '-'}</div>
                  <div><strong>Status:</strong> {serverStatus}</div>
                  <div><strong>Orphan VMs:</strong> {summary.stoppedVmCount}</div>
                </div>
              </div>

              {/* CLUSTERS */}
              <div className="card">
                <div className="card-header">Clusters & Nodes</div>
                <div className="card-body">
                  {clusters.length === 0 && (
                    <div className="text-muted">Žádné clustery.</div>
                  )}

                  {clusters.map((cluster) => (
                    <div key={cluster.id} className="mb-3">
                      <strong>{cluster.name}</strong>
                      <div className="small text-muted mb-2">
                        Nodes: {(cluster.nodes || []).length}
                      </div>

                      {(cluster.nodes || []).map((node) => (
                        <div key={node.id} className="border p-2 mb-2">
                          <div className="d-flex justify-content-between">
                            <div>
                              <strong>{node.name}</strong>
                              <div className="small text-muted">{node.host}</div>
                            </div>

                            <span className={`badge ${
                              node.status === 'online' || node.status === 'running'
                                ? 'bg-success'
                                : 'bg-secondary'
                            }`}>
                              {node.status}
                            </span>
                          </div>

                          <div className="small mt-1">
                            VMs: {(node.items || []).filter(i => i.type === 'vm').length} | 
                            Templates: {(node.items || []).filter(i => i.type === 'template').length}
                          </div>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>

            </div>
          )}

          {activeTab === 'automation' && (
            <ServerAutomation
              serverId={selectedItem.id}
              selectedItem={selectedItem}
              onRefreshServers={onRefreshServers}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default ServerDetail;