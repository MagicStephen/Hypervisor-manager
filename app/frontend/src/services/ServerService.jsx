const API_BASE = process.env.REACT_APP_VPM_API_URL;

export async function fetchServers() {
  const res = await fetch(`${API_BASE}/servers/`, {
    method: 'GET',
    credentials: 'include'
  });

  const result = await res.json();

  if (!res.ok) {
    const error = new Error(result?.message || 'Server retrieve failed');
    error.result = result;
    throw error;
  }

  return result;
}

export async function serverConnect(platform, credentials) {
  
  const res = await fetch(`${API_BASE}/servers/${platform}/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
    credentials: 'include'
  });

  const result = await res.json();

  if (!res.ok) {
    throw new Error(result.message || 'Reconnect failed');
  }

  return result;
}

export async function serverReconnect(serverId, password) {
  const res = await fetch(`${API_BASE}/servers/reconnect/${serverId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
    credentials: 'include'
  });

  const result = await res.json();

  if (!res.ok) {
    throw new Error(result.message || 'Reconnect failed');
  }

  return result;
}