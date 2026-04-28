import React from 'react';
import Icon from '../Common/Icon';

function VmTreeItem({
  serverId,
  clusterId,
  nodeId,
  vm,
  selectedItem,
  onSelect
}) {
  const isSelected =
    selectedItem?.type === vm.type &&
    selectedItem?.id === vm.id;

  function handleClick() {
    onSelect({
      ...vm,
      serverId,
      clusterId,
      nodeId
    });
  }

  const isTemplate = vm.type === 'template';

  return (
    <div
      className={`d-flex align-items-center px-2 py-1 mt-1 rounded ${
        isSelected ? 'bg-warning-subtle' : ''
      }`}
      style={{ cursor: 'pointer', fontSize: '12px' }}
      onClick={handleClick}
    >
      <Icon
        name={isTemplate ? 'template' : 'vm'}
        size="sm"
        className="me-2 text-muted"
      />

      <div className="flex-grow-1 d-flex align-items-center justify-content-between">
        <span>{vm.name}</span>

        <span
          className={`rounded-circle ${
            vm.status === 'running' ? 'bg-success' : 'bg-danger'
          }`}
          style={{ width: '8px', height: '8px' }}
        />
      </div>
    </div>
  );
}

export default VmTreeItem;