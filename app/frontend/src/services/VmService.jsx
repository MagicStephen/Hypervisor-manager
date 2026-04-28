const API_BASE = process.env.REACT_APP_VPM_API_URL;

export async function CreateVm(serverId, nodeId, payload = {}) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include',
      body: JSON.stringify(payload)
    }
  );

  const result = await res.json();

  return result;
}

export async function DropVm(serverId, nodeId, vmId) {

  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include',
    }
  );

  if (!res.ok) {
    let message = 'VM snapshot rollback failed';

    try {
      const err = await res.json();
      message = err?.detail || err?.message || message;
    } catch {}

    throw new Error(message);
  } 

}

export async function GetVmSnapshots(serverId, nodeId, vmId) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}/snapshots?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include',
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'VM snapshots fetch failed');
    error.result = result;
    throw error;
  }

  return result;
}

export async function CreateVmSnapshot(serverId, nodeId, vmId, parameters) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}/snapshot?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include',
      body: JSON.stringify(parameters)
    }
  );

  if (!res.ok) {
    let message = 'VM snapshot rollback failed';

    try {
      const err = await res.json();
      message = err?.detail || err?.message || message;
    } catch {}

    throw new Error(message);
  }
}

export async function DropVmSnapshot(serverId, nodeId, vmId, snapshotId) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}/snapshot/${snapshotId}?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include',
    }
  );

  if (!res.ok) {
    let message = 'VM snapshot rollback failed';

    try {
      const err = await res.json();
      message = err?.detail || err?.message || message;
    } catch {}

    throw new Error(message);
  }
}

export async function RollbackVmSnapshot(serverId, nodeId, vmId, snapshotId) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}/snapshot/${snapshotId}?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include',
    }
  );

  if (!res.ok) {
    let message = 'VM snapshot rollback failed';

    try {
      const err = await res.json();
      message = err?.detail || err?.message || message;
    } catch {}

    throw new Error(message);
  } 
}

export async function fetchVmCapabilities(serverId, nodeId, vmId = 'new') {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}/capabilities?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'VM capabilities fetch failed');
    error.result = result;
    throw error;
  }

  return result;
}

export async function fetchVmConfiguration(serverId, nodeId, vmId) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}/config?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include'
    }
  );

  const result = await res.json();

  console.log(result);

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'VM config fetch failed');
    error.result = result;
    throw error;
  }

  return result;
}

export async function updateVmConfiguration(serverId, nodeId, vmId, payload) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}/config?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify(payload),
    }
  );

  if (!res.ok) {
    let message = 'VM snapshot rollback failed';

    try {
      const err = await res.json();
      message = err?.detail || err?.message || message;
    } catch {}

    throw new Error(message);
  } 
}

export async function GetVmBackups(serverId, nodeId, vmId) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}/backups?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'VM backups fetch failed');
    error.result = result;
    throw error;
  }

  return result;
}

export async function CreateVmBackup(serverId, nodeId, vmId) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}/backup?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    }
  );

  if (!res.ok) {
    let message = 'VM snapshot rollback failed';

    try {
      const err = await res.json();
      message = err?.detail || err?.message || message;
    } catch {}

    throw new Error(message);
  } 
}

export async function GetVmConsole(serverId, nodeId, vmId, protocol) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}/console/${protocol}?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'VM console fetch failed');
    error.result = result;
    throw error;
  }

  return result;
}

export async function fetchVmStatus(serverId, nodeId, vmId, fields = []) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}/status?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include',
      body: JSON.stringify({
        fields
      })
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'VM status fetch failed');
    error.result = result;
    throw error;
  }

  return result;
}

export async function SetVmStatus(serverId, nodeId, vmId, status) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}/status/${status}?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include'
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'VM status update failed');
    error.result = result;
    throw error;
  }

  return result;
}

export async function fetchVmTimeMetrics(serverId, nodeId, vmId, payload) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}/timemetrics?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify(payload),
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'VM time metrics fetch failed');
    error.result = result;
    throw error;
  }

  return result;
}

export async function fetchVmLogs(serverId, nodeId, vmId, limit) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/vms/${vmId}/logs/${limit}?nodeid=${encodeURIComponent(nodeId)}`,
    {
      method: 'GET',
      credentials: 'include'
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'VM logs fetch failed');
    error.result = result;
    throw error;
  }

  return result;
}