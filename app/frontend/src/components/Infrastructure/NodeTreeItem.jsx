import React from 'react';
import Icon from '../Common/Icon';
import VmTreeItem from './VmTreeItem';

function NodeTreeItem({
  serverId,
  clusterId,
  node,
  selectedItem,
  onSelect,
  onToggleNode
}) {
  const isSelected =
    selectedItem?.type === 'node' &&
    selectedItem?.serverId === serverId &&
    selectedItem?.clusterId === clusterId &&
    selectedItem?.id === node.id;
    

  const items = node.items || [];
  const vms = items.filter((item) => item.type === 'vm');
  const templates = items.filter((item) => item.type === 'template');

  const hasItems = items.length > 0;
  const toggleIcon = node.expanded ? '▾' : '▸';

  function handleSelectNode() {
    onSelect({
      ...node,
      type: 'node',
      serverId,
      clusterId,
      platform: node.platform
    });
  }

  function handleToggle(e) {
    e.stopPropagation();
    if (!hasItems) return;
    onToggleNode(serverId, clusterId, node.id);
  }

  return (
    <div className="mt-1">
      <div
        className={`d-flex align-items-center px-2 py-1 rounded ${
          isSelected ? 'bg-info text-dark' : 'bg-white'
        }`}
        style={{
          cursor: 'pointer',
          fontSize: '13px'
        }}
        onClick={handleSelectNode}
      >
        <Icon
          name="node"
          size="sm"
          className={`me-2 ${isSelected ? 'text-white' : 'text-dark'}`}
        />

        <div className="flex-grow-1 d-flex align-items-center justify-content-between">
          <div className="d-flex align-items-center">
            <strong>{node.name}</strong>

            <span
              className={`ms-2 rounded-circle ${
                node.status ? 'bg-success' : 'bg-danger'
              }`}
              style={{ width: '8px', height: '8px' }}
            />
          </div>

          <span
            onClick={handleToggle}
            style={{
              fontSize: '12px',
              padding: '0 4px',
              cursor: hasItems ? 'pointer' : 'default',
              opacity: hasItems ? 1 : 0.3
            }}
          >
            {toggleIcon}
          </span>
        </div>
      </div>

      {node.expanded && hasItems && (
        <div className="ps-3">
          {vms.length > 0 && (
            <div className="mt-1">
              {vms.map((item) => (
                <VmTreeItem
                  key={`vm-${item.id}`}
                  serverId={serverId}
                  clusterId={clusterId}
                  nodeId={node.id}
                  vm={item}
                  selectedItem={selectedItem}
                  onSelect={onSelect}
                />
              ))}
            </div>
          )}

          {templates.length > 0 && (
            <div className="mt-2">
              <div className="px-2 py-1 text-muted" style={{ fontSize: '12px' }}>
                Templates
              </div>

              <div className="ps-2">
                {templates.map((item) => (
                  <VmTreeItem
                    key={`template-${item.id}`}
                    serverId={serverId}
                    clusterId={clusterId}
                    nodeId={node.id}
                    vm={item}
                    selectedItem={selectedItem}
                    onSelect={onSelect}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default NodeTreeItem;