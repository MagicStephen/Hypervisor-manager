import React from 'react';
import ClusterTreeItem from './ClusterTreeItem';
import Icon from '../Common/Icon';

function ServerTreeItem({
  server,
  selectedItem,
  onSelect,
  onToggleServer,
  onToggleCluster,
  onToggleNode
}) {
  const isSelected =
    selectedItem?.type === 'server' &&
    selectedItem?.id === server.id;

  function handleClick() {
    onSelect(server);
  }

  function handleToggle(e) {
    e.stopPropagation();
    onToggleServer(server.id);
  }

  const toggleIcon = server.expanded ? '▾' : '▸';

  return (
    <div className="border rounded bg-white overflow-hidden">
      <div
        className={`px-2 py-2 ${isSelected ? 'bg-primary text-white' : ''}`}
        style={{ cursor: 'pointer' }}
        onClick={handleClick}
      >
        <div className="d-flex align-items-center">
          <Icon
            name="server"
            size="lg"
            className={`me-2 ${isSelected ? 'text-white' : 'text-dark'}`}
          />

          <div className="flex-grow-1">
            <div className="d-flex align-items-center">
              <strong>{server.name}</strong>
            </div>

            <div
              style={{ fontSize: '12px' }}
              className={isSelected ? 'text-white-50' : 'text-muted'}
            >
              {server.platform} / {server.host}
            </div>
          </div>

          <span
            className={`ms-auto ${isSelected ? 'text-white' : 'text-muted'}`}
            style={{ fontSize: '14px', lineHeight: 1, cursor: 'pointer' }}
            onClick={handleToggle}
          >
            {toggleIcon}
          </span>
        </div>
      </div>

      {server.connected && server.expanded && server.clusters?.length > 0 && (
        <div className="ps-3 pb-2">
          {server.clusters.map((cluster) => (
            <ClusterTreeItem
              key={cluster.id}
              serverId={server.id}
              cluster={cluster}
              selectedItem={selectedItem}
              onSelect={onSelect}
              onToggleCluster={onToggleCluster}
              onToggleNode={onToggleNode}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default ServerTreeItem;