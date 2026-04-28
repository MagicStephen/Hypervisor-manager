const API_BASE = process.env.REACT_APP_VPM_API_URL;

export async function setAutomationAuth(serverId, credentials) {
  try {
    const res = await fetch(`${API_BASE}/servers/${serverId}/tasks/automation-auth`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
      credentials: 'include'
    });

    const result = await res.json();

    if (!res.ok) {
      return {
        success: false,
        message: result?.detail || 'Setting automation auth failed',
        data: null
      };
    }

    return {
      success: true,
      message: 'Automation auth set successfully',
      data: result
    };
  } catch (err) {
    console.error('setAutomationAuth error:', err);

    return {
      success: false,
      message: 'Network error',
      data: null
    };
  }
}

export async function getAutomationAuth(serverId) {
  try {
    const res = await fetch(`${API_BASE}/servers/${serverId}/tasks/automation-auth`, {
      method: 'GET',
      credentials: 'include'
    });

    const result = await res.json();

    if (!res.ok) {
      return {
        success: false,
        data: null
      };
    }

    return {
      success: true,
      data: result
    };
  } catch (err) {
    console.error('getAutomationAuth error:', err);

    return {
      success: false,
      data: null
    };
  }
}

export async function fetchAutomationTasks(serverId) {
  try {
    const res = await fetch(`${API_BASE}/servers/${serverId}/tasks/automation-tasks`, {
      method: 'GET',
      credentials: 'include'
    });

    const result = await res.json();

    if (!res.ok) {
      return {
        success: false,
        message: result?.detail || 'Automation tasks fetch failed',
        data: []
      };
    }

    return {
      success: true,
      message: 'Automation tasks loaded successfully',
      data: Array.isArray(result) ? result : []
    };
  } catch (err) {
    console.error('fetchAutomationTasks error:', err);

    return {
      success: false,
      message: 'Network error',
      data: []
    };
  }
}

export async function createAutomationTask(serverId, taskData) {
  try {
    const res = await fetch(`${API_BASE}/servers/${serverId}/tasks/automation-task`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(taskData),
      credentials: 'include'
    });

    const result = await res.json();

    if (!res.ok) {
      return {
        success: false,
        message: result?.detail || 'Automation task creation failed',
        data: null,
        taskId: null
      };
    }

    return {
      success: true,
      message: 'Automation task created successfully',
      data: result,
      taskId: result.id ?? null
    };
  } catch (err) {
    console.error('createAutomationTask error:', err);

    return {
      success: false,
      message: 'Network error',
      data: null,
      taskId: null
    };
  }
}

export async function deleteAutomationTask(serverId, taskId) {
  try {
    const res = await fetch(`${API_BASE}/servers/${serverId}/tasks/automation-task/${taskId}`, {
      method: 'DELETE',
      credentials: 'include'
    });

    const result = await res.json();

    if (!res.ok) {
      return {
        success: false,
        message: result?.detail || 'Automation task delete failed',
        data: null
      };
    }

    return {
      success: true,
      message: 'Automation task deleted successfully',
      data: result
    };
  } catch (err) {
    console.error('deleteAutomationTask error:', err);

    return {
      success: false,
      message: 'Network error',
      data: null
    };
  }
}