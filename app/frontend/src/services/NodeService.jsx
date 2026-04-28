const API_BASE = process.env.REACT_APP_VPM_API_URL;

export async function fetchNodeStatus(serverId, nodeId, fields = []) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/nodes/${nodeId}/status`,
    {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ fields })
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'Node status retrieve failed');
    error.result = result;
    throw error;
  }

  return result;
}

export async function fetchNodeMetrics(serverId, nodeId, options = {}) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/nodes/${nodeId}/metrics`,
    {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(options)
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'Node metrics retrieve failed');
    error.result = result;
    throw error;
  }

  return result;
}

export async function fetchNodeStorage(serverId, nodeId) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/nodes/${nodeId}/storage`,
    {
      method: 'POST',
      credentials: 'include'
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'Node storage retrieve failed');
    error.result = result;
    throw error;
  }

  return result;
}

export async function fetchNodeStorageContent(serverId, nodeId, storageId) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/nodes/${nodeId}/storage/${storageId}/content`,
    {
      method: 'POST',
      credentials: 'include'
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'Node storage content retrieve failed');
    error.result = result;
    throw error;
  }

  return result;
}

export async function deleteNodeStorageContent(serverId, nodeId, storageId, volId) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/nodes/${nodeId}/storage/${storageId}/content/${encodeURIComponent(volId)}`,
    {
      method: 'DELETE',
      credentials: 'include'
    }
  );

  const result = await res.json();

  if (!res.ok) {
    let message = 'Delete node storage content failed';

    const detail = result?.detail || result?.message;

    if (detail) {
      if (typeof detail === 'string') {
        message = detail;
      } else {
        message = JSON.stringify(detail, null, 2);
      }
    }

    const error = new Error(message);
    error.result = result;
    throw error;
  }

  return result;
}

export async function uploadNodeStorageFile(
  serverId,
  nodeId,
  storageId,
  content,
  file,
  onProgress
) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('content', content);
    formData.append('file', file);

    const xhr = new XMLHttpRequest();

    xhr.open(
      'POST',
      `${API_BASE}/servers/${serverId}/nodes/${nodeId}/storage/${storageId}/upload`,
      true
    );

    xhr.withCredentials = true;

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        const percent = Math.round((event.loaded / event.total) * 100);
        onProgress(percent);
      }
    };

    xhr.onload = () => {
      try {
        const result = xhr.responseText ? JSON.parse(xhr.responseText) : null;

        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(result);
          return;
        }

        const detail = result?.detail || result?.message;

        let message = `Upload failed with status ${xhr.status}`;

        if (detail) {
          if (typeof detail === 'string') {
            message = detail;
          } else {
            message = JSON.stringify(detail, null, 2);
          }
        }

        const error = new Error(message);
        error.result = result;
        reject(error);
      } catch (error) {
        reject(error);
      }
    };

    xhr.onerror = () => {
      reject(new Error('Network error'));
    };

    xhr.send(formData);
  });
}

export async function createNodeConsoleSession(serverId, nodeId) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/nodes/${nodeId}/console/token`,
    {
      method: 'POST',
      credentials: 'include'
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'Create node console session failed');
    error.result = result;
    throw error;
  }

  return result;
}

export function getNodeConsoleWsUrl(serverId, nodeId, token) {
  const wsBase = API_BASE
    .replace('http://', 'ws://')
    .replace('https://', 'wss://');

  return `${wsBase}/servers/${serverId}/nodes/${nodeId}/console?token=${encodeURIComponent(token)}`;
}

export async function fetchNodeNetworks(serverId, nodeId) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/nodes/${nodeId}/networks`,
    {
      method: 'GET',
      credentials: 'include'
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'Node logs retrieve failed');
    error.result = result;
    throw error;
  }

  return result;
}

export async function fetchNodeLogs(serverId, nodeId, limit=1500) {
  const res = await fetch(
    `${API_BASE}/servers/${serverId}/nodes/${nodeId}/logs/${limit}`,
    {
      method: 'POST',
      credentials: 'include'
    }
  );

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.detail || result?.message || 'Node logs retrieve failed');
    error.result = result;
    throw error;
  }

  return result;
}