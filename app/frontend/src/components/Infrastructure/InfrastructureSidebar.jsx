import React from 'react';
import InfrastructureTree from './InfrastructureTree';

function InfrastructureSidebar({
  servers,
  loading,
  selectedItem,
  onSelect,
  onToggleServer,
  onToggleCluster,
  onToggleNode,
  onAddServer
}) {
  return (
    <div
      className="card h-100"
      style={{ width: '380px', minWidth: '380px' }}
    >
      <div className="card-header d-flex justify-content-between align-items-center">
        <strong>Servers</strong>
        <button className="btn btn-sm btn-primary" onClick={onAddServer}>
          + Add
        </button>
      </div>

      <div className="card-body p-2 overflow-y-auto">
        <InfrastructureTree
          servers={servers || []}
          loading={loading}
          selectedItem={selectedItem}
          onSelect={onSelect}
          onToggleServer={onToggleServer}
          onToggleCluster={onToggleCluster}
          onToggleNode={onToggleNode}
        />
      </div>
    </div>
  );
}

export default InfrastructureSidebar;