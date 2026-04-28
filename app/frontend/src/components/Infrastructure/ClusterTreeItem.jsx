import React from 'react';
import NodeTreeItem from './NodeTreeItem';
import VmTreeItem from './VmTreeItem';
import Icon from '../Common/Icon';

function ClusterTreeItem({
  serverId,
  cluster,
  selectedItem,
  onSelect,
  onToggleCluster,
  onToggleNode
}) {
  const isSelected =
    selectedItem?.type === 'cluster' &&
    selectedItem?.serverId === serverId &&
    selectedItem?.id === cluster.id;

  function handleClick() {
    onSelect({
      ...cluster,
      type: 'cluster',
      serverId,
      platform: cluster.platform
    });
  }

  function handleToggle(e) {
    e.stopPropagation();
    onToggleCluster(serverId, cluster.id);
  }

  const toggleIcon = cluster.expanded ? '▾' : '▸';
  const hasNodes = cluster.nodes?.length > 0;
  const hasOrphanVms = cluster.orphanVms?.length > 0;
  const hasTemplates = cluster.templates?.length > 0;

  return (
    <div className="pt-2 pe-2">
      <div
        className={`px-2 py-2 rounded border ${
          isSelected
            ? 'bg-secondary text-white border-secondary'
            : 'bg-light border-light-subtle'
        }`}
        style={{ cursor: 'pointer' }}
        onClick={handleClick}
      >
        <div className="d-flex align-items-center">
          <div className="d-flex align-items-center flex-grow-1">
            <Icon
              name="cluster"
              size="sm"
              className={`me-2 ${isSelected ? 'text-white' : 'text-dark'}`}
            />
            <strong>{cluster.name}</strong>
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

      {cluster.expanded && (
        <div className="ps-3 mt-2">
          {hasNodes &&
            cluster.nodes.map((node) => (
              <NodeTreeItem
                key={node.id}
                serverId={serverId}
                clusterId={cluster.id}
                node={node}
                selectedItem={selectedItem}
                onSelect={onSelect}
                onToggleNode={onToggleNode}
              />
            ))}

          {hasOrphanVms && (
            <div className="mt-2">
              <div className="px-2 py-1 text-muted" style={{ fontSize: '12px' }}>
                Stopped VMs
              </div>

              <div className="ps-2">
                {cluster.orphanVms.map((vm) => (
                  <VmTreeItem
                    key={`vm-${vm.id}`}
                    serverId={serverId}
                    clusterId={cluster.id}
                    nodeId={vm.nodeId ?? vm.preferredNode?.id ?? null}
                    vm={vm}
                    selectedItem={selectedItem}
                    onSelect={onSelect}
                  />
                ))}
              </div>
            </div>
          )}

          {hasTemplates && (
            <div className="mt-2">
              <div className="px-2 py-1 text-muted" style={{ fontSize: '12px' }}>
                Templates
              </div>

              <div className="ps-2">
                {cluster.templates.map((template) => (
                  <VmTreeItem
                    key={`template-${template.id}`}
                    serverId={serverId}
                    clusterId={cluster.id}
                    nodeId={template.nodeId ?? null}
                    vm={template}
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

export default ClusterTreeItem;