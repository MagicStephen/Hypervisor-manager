import React from 'react';
import ServerTreeItem from './ServerTreeItem';

function InfrastructureTree({
  servers,
  loading,
  selectedItem,
  onSelect,
  onToggleServer,
  onToggleCluster,
  onToggleNode
}) {
  if (loading) {
    return <div>Loading servers...</div>;
  }

  if (!servers.length) {
    return <div className="text-muted">No servers added yet.</div>;
  }

  return (
    <div className="d-flex flex-column gap-2">
      {servers.map((server) => (
        <ServerTreeItem
          key={server.id}
          server={server}
          selectedItem={selectedItem}
          onSelect={onSelect}
          onToggleServer={onToggleServer}
          onToggleCluster={onToggleCluster}
          onToggleNode={onToggleNode}
        />
      ))}
    </div>
  );
}

export default InfrastructureTree;