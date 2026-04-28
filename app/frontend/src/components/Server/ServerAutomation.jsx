import React, { useEffect, useMemo, useState } from 'react';
import {
  fetchAutomationTasks,
  createAutomationTask,
  deleteAutomationTask,
  setAutomationAuth,
  getAutomationAuth
} from '../../services/AutomationService';

function createEmptyStep(defaultVmId = '', defaultNodeId = '') {
  return {
    name: '',
    vm_id: defaultVmId,
    node_id: defaultNodeId,
    action: 'start',
    snapshot_name: '',
    duration_seconds: ''
  };
}

function ServerAutomation({ serverId, selectedItem, onRefreshServers }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submittingWorkflow, setSubmittingWorkflow] = useState(false);
  const [authInfo, setAuthInfo] = useState(null);
  const [collapsedTaskIds, setCollapsedTaskIds] = useState(() => new Set());

  const [authForm, setAuthForm] = useState({
    username: '',
    password: ''
  });

  const [workflowForm, setWorkflowForm] = useState({
    name: '',
    trigger_type: 'cron',
    cron_expression: '',
    interval_seconds: '',
    run_at: '',
    enabled: true
  });

  const [steps, setSteps] = useState([createEmptyStep()]);

  const nodeOptions = useMemo(() => {
    const clusters = selectedItem?.clusters || [];

    return clusters.flatMap((cluster) =>
      (cluster.nodes || []).map((node) => ({
        node_id: String(node.id),
        label: node.name
      }))
    );
  }, [selectedItem]);

  const vmOptions = useMemo(() => {
    const clusters = selectedItem?.clusters || [];

    return clusters.flatMap((cluster) =>
      (cluster.nodes || []).flatMap((node) =>
        (node.items || [])
          .filter((item) => item.type === 'vm')
          .map((item) => ({
            vm_id: String(item.id),
            node_id: String(node.id),
            label: `${item.name} (${node.name})`,
            nodeName: node.name
          }))
      )
    );
  }, [selectedItem]);

  useEffect(() => {
    if (!serverId) return;
    loadData();
  }, [serverId]);

  async function loadData() {
    try {
      setLoading(true);

      const [tasksResult, authResult] = await Promise.all([
        fetchAutomationTasks(serverId),
        getAutomationAuth(serverId)
      ]);

      if (tasksResult?.success) {
        setTasks(Array.isArray(tasksResult.data) ? tasksResult.data : []);
      } else {
        setTasks([]);
      }

      if (authResult?.success) {
        setAuthInfo(authResult.data || null);
      } else {
        setAuthInfo(null);
      }
    } catch (err) {
      console.error('Error loading automation data:', err);
      setTasks([]);
      setAuthInfo(null);
    } finally {
      setLoading(false);
    }
  }

  function toggleTaskCollapse(taskId) {
    setCollapsedTaskIds((prev) => {
      const next = new Set(prev);

      if (next.has(taskId)) {
        next.delete(taskId);
      } else {
        next.add(taskId);
      }

      return next;
    });
  }

  function resetWorkflowForm() {
    setWorkflowForm({
      name: '',
      trigger_type: 'cron',
      cron_expression: '',
      interval_seconds: '',
      run_at: '',
      enabled: true
    });
    setSteps([createEmptyStep()]);
  }

  function handleWorkflowChange(e) {
    const { name, value, type, checked } = e.target;

    setWorkflowForm((prev) => {
      const next = {
        ...prev,
        [name]: type === 'checkbox' ? checked : value
      };

      if (name === 'trigger_type') {
        if (value !== 'cron') next.cron_expression = '';
        if (value !== 'interval') next.interval_seconds = '';
        if (value !== 'once') next.run_at = '';
      }

      return next;
    });
  }

  function handleStepChange(index, e) {
    const { name, value } = e.target;

    setSteps((prev) =>
      prev.map((step, i) => {
        if (i !== index) return step;

        const next = {
          ...step,
          [name]: value
        };

        if (name === 'vm_id') {
          const selectedVm = vmOptions.find((vm) => String(vm.vm_id) === String(value));
          next.node_id = selectedVm ? selectedVm.node_id : '';
        }

        if (name === 'action' && value !== 'snapshot') {
          next.snapshot_name = '';
        }

        return next;
      })
    );
  }

  function addStep() {
    setSteps((prev) => {
      const last = prev[prev.length - 1];
      return [...prev, createEmptyStep(last?.vm_id || '', last?.node_id || '')];
    });
  }

  function removeStep(index) {
    setSteps((prev) => {
      if (prev.length === 1) return prev;
      return prev.filter((_, i) => i !== index);
    });
  }

  function moveStepUp(index) {
    if (index === 0) return;

    setSteps((prev) => {
      const copy = [...prev];
      [copy[index - 1], copy[index]] = [copy[index], copy[index - 1]];
      return copy;
    });
  }

  function moveStepDown(index) {
    setSteps((prev) => {
      if (index === prev.length - 1) return prev;
      const copy = [...prev];
      [copy[index], copy[index + 1]] = [copy[index + 1], copy[index]];
      return copy;
    });
  }

  function handleAuthChange(e) {
    const { name, value } = e.target;

    setAuthForm((prev) => ({
      ...prev,
      [name]: value
    }));
  }

  async function handleAuthSubmit(e) {
    e.preventDefault();

    const payload = {
      username: authForm.username.trim(),
      password: authForm.password
    };

    try {
      const result = await setAutomationAuth(serverId, payload);

      if (result?.success) {
        setAuthForm({
          username: '',
          password: ''
        });

        setAuthInfo(result.data || null);
        await loadData();
      } else {
        console.error(result?.message || 'Failed to set automation auth');
      }
    } catch (err) {
      console.error('Error setting automation auth:', err);
    }
  }

  async function handleDeleteTask(taskId) {
    try {
      const result = await deleteAutomationTask(serverId, taskId);

      if (result?.success) {
        await loadData();

        if (onRefreshServers) {
          await onRefreshServers();
        }
      } else {
        console.error(result?.message || 'Failed to delete automation task');
      }
    } catch (err) {
      console.error('Error deleting automation task:', err);
    }
  }

  async function handleSubmitWorkflow(e) {
    e.preventDefault();

    const validSteps = steps.filter(
      (step) =>
        step.name.trim() &&
        step.vm_id &&
        step.node_id &&
        step.action
    );

    if (!workflowForm.name.trim()) {
      console.error('Workflow name is required');
      return;
    }

    if (validSteps.length === 0) {
      console.error('At least one workflow step is required');
      return;
    }

    const rootPayload = {
      name: workflowForm.name.trim(),
      enabled: workflowForm.enabled,
      vm_id: Number(validSteps[0].vm_id),
      node_id: String(validSteps[0].node_id),
      action: validSteps[0].action,
      trigger_type: workflowForm.trigger_type
    };

    if (workflowForm.trigger_type === 'cron') {
      rootPayload.cron_expression = workflowForm.cron_expression.trim();
    }

    if (workflowForm.trigger_type === 'interval') {
      rootPayload.interval_seconds = workflowForm.interval_seconds
        ? Number(workflowForm.interval_seconds)
        : null;
    }

    if (workflowForm.trigger_type === 'once') {
      rootPayload.run_at = workflowForm.run_at || null;
    }

    if (validSteps[0].action === 'snapshot' && validSteps[0].snapshot_name.trim()) {
      rootPayload.snapshot_name = validSteps[0].snapshot_name.trim();
    }

    if (validSteps[0].duration_seconds) {
      rootPayload.duration_seconds = Number(validSteps[0].duration_seconds);
    }

    setSubmittingWorkflow(true);

    try {
      const rootResult = await createAutomationTask(serverId, rootPayload);

      if (!rootResult?.success || !rootResult?.data?.id) {
        console.error(rootResult?.message || 'Failed to create workflow root task');
        return;
      }

      const rootTaskId = rootResult.data.id;

      for (let i = 1; i < validSteps.length; i += 1) {
        const step = validSteps[i];

        const childPayload = {
          name: step.name.trim(),
          vm_id: Number(step.vm_id),
          node_id: String(step.node_id),
          action: step.action,
          enabled: true,
          parent_id: rootTaskId,
          order_index: i - 1
        };

        if (step.action === 'snapshot' && step.snapshot_name.trim()) {
          childPayload.snapshot_name = step.snapshot_name.trim();
        }

        if (step.duration_seconds) {
          childPayload.duration_seconds = Number(step.duration_seconds);
        }

        const childResult = await createAutomationTask(serverId, childPayload);

        if (!childResult?.success || !childResult?.data?.id) {
          console.error(`Failed to create child step ${i}:`, childResult?.message);
          return;
        }
      }

      resetWorkflowForm();
      await loadData();

      if (onRefreshServers) {
        await onRefreshServers();
      }
    } catch (err) {
      console.error('Error creating workflow:', err);
    } finally {
      setSubmittingWorkflow(false);
    }
  }

  function renderTaskList(items, level = 0) {
  return (
      <div className="d-flex flex-column gap-2">
        {items.map((task) => {
          const children = tasks
            .filter((item) => item.parent_id === task.id)
            .sort((a, b) => {
              if ((a.order_index ?? 0) !== (b.order_index ?? 0)) {
                return (a.order_index ?? 0) - (b.order_index ?? 0);
              }
              return a.id - b.id;
            });

          const hasChildren = children.length > 0;
          const isExpanded = collapsedTaskIds.has(task.id);

          return (
            <div
              key={task.id}
              className="border rounded p-2"
              style={{ marginLeft: `${level * 24}px` }}
            >
              <div className="d-flex justify-content-between align-items-center gap-2 flex-wrap">
                <div className="d-flex align-items-center gap-2 flex-wrap">
                  <strong>{task.name}</strong>

                  <span className={`badge ${task.parent_id ? 'bg-secondary' : 'bg-primary'}`}>
                    {task.parent_id ? 'child' : 'root'}
                  </span>

                  {hasChildren && (
                    <span className="badge bg-secondary">
                      {children.length} steps
                    </span>
                  )}

                  <span className="text-muted small">
                    Action: {task.action}
                  </span>

                  <span className="text-muted small">
                    Trigger: {task.trigger_type || '-'}
                  </span>

                  <span className="text-muted small">
                    Order: {task.order_index ?? 0}
                  </span>

                  {task.cron_expression && (
                    <span className="text-muted small">
                      Cron: {task.cron_expression}
                    </span>
                  )}

                  {task.interval_seconds && (
                    <span className="text-muted small">
                      Interval: {task.interval_seconds}s
                    </span>
                  )}

                  {task.run_at && (
                    <span className="text-muted small">
                      Run at: {task.run_at}
                    </span>
                  )}

                  {task.snapshot_name && (
                    <span className="text-muted small">
                      Snapshot: {task.snapshot_name}
                    </span>
                  )}

                  {task.duration_seconds && (
                    <span className="text-muted small">
                      Duration: {task.duration_seconds}s
                    </span>
                  )}
                </div>

                <div className="d-flex gap-2 ms-auto">
                  {hasChildren && (
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-secondary"
                      onClick={() => toggleTaskCollapse(task.id)}
                    >
                      {isExpanded ? 'Hide' : 'Show'}
                    </button>
                  )}

                  <button
                    type="button"
                    className="btn btn-sm btn-outline-danger"
                    onClick={() => handleDeleteTask(task.id)}
                  >
                    Delete
                  </button>
                </div>
              </div>

              {hasChildren && !isExpanded  && (
                <div className="mt-2">
                  {renderTaskList(children, level + 1)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  const rootTasks = useMemo(() => {
    return [...tasks]
      .filter((task) => task.parent_id == null)
      .sort((a, b) => {
        if ((a.order_index ?? 0) !== (b.order_index ?? 0)) {
          return (a.order_index ?? 0) - (b.order_index ?? 0);
        }
        return a.id - b.id;
      });
  }, [tasks]);

  const authConfigured = authInfo?.configured;

  return (
    <div className="d-flex flex-column gap-3">
      <div className="card">
        <div className="card-header">Automation info</div>
        <div className="card-body">
          <div>
            <strong>Server:</strong> {selectedItem?.name}
          </div>
          <div>
            <strong>Automation auth:</strong>{' '}
            {authConfigured ? 'Configured' : 'Not configured'}
          </div>

          {authConfigured && (
            <>
              <div>
                <strong>Username:</strong> {authInfo?.username || '-'}
              </div>
              <div>
                <strong>Token auth:</strong> {authInfo?.has_token ? 'Yes' : 'No'}
              </div>
              <div>
                <strong>Password auth:</strong> {authInfo?.has_password ? 'Yes' : 'No'}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header">Set automation auth</div>
        <div className="card-body">
          <form onSubmit={handleAuthSubmit}>
            <div className="mb-3">
              <label className="form-label">Username</label>
              <input
                type="text"
                name="username"
                value={authForm.username}
                onChange={handleAuthChange}
                className="form-control"
                required
              />
            </div>

            <div className="mb-3">
              <label className="form-label">Password</label>
              <input
                type="password"
                name="password"
                value={authForm.password}
                onChange={handleAuthChange}
                className="form-control"
                required
              />
            </div>

            <button type="submit" className="btn btn-secondary">
              Save auth
            </button>
          </form>
        </div>
      </div>

      {!authConfigured && (
        <div className="alert alert-warning mb-0">
          Pro tento server není nastavený automation auth. Task sice můžeš vytvořit,
          ale prakticky dává smysl nejdřív nastavit přístupové údaje.
        </div>
      )}

      <div className="card">
        <div className="card-header">Create workflow</div>
        <div className="card-body">
          <form onSubmit={handleSubmitWorkflow}>
            <div className="mb-3">
              <label className="form-label">Workflow name</label>
              <input
                type="text"
                name="name"
                value={workflowForm.name}
                onChange={handleWorkflowChange}
                className="form-control"
                required
              />
            </div>

            <div className="row">
              <div className="col-md-6 mb-3">
                <label className="form-label">Trigger type</label>
                <select
                  name="trigger_type"
                  value={workflowForm.trigger_type}
                  onChange={handleWorkflowChange}
                  className="form-select"
                  required
                >
                  <option value="cron">cron</option>
                  <option value="interval">interval</option>
                  <option value="once">once</option>
                </select>
              </div>

              <div className="col-md-6 mb-3 d-flex align-items-end">
                <div className="form-check">
                  <input
                    type="checkbox"
                    name="enabled"
                    checked={workflowForm.enabled}
                    onChange={handleWorkflowChange}
                    className="form-check-input"
                    id="enabled-workflow"
                  />
                  <label className="form-check-label" htmlFor="enabled-workflow">
                    Enabled
                  </label>
                </div>
              </div>
            </div>

            {workflowForm.trigger_type === 'cron' && (
              <div className="mb-3">
                <label className="form-label">Cron expression</label>
                <input
                  type="text"
                  name="cron_expression"
                  value={workflowForm.cron_expression}
                  onChange={handleWorkflowChange}
                  className="form-control"
                  placeholder="*/5 * * * *"
                  required
                />
              </div>
            )}

            {workflowForm.trigger_type === 'interval' && (
              <div className="mb-3">
                <label className="form-label">Interval seconds</label>
                <input
                  type="number"
                  min="1"
                  name="interval_seconds"
                  value={workflowForm.interval_seconds}
                  onChange={handleWorkflowChange}
                  className="form-control"
                  required
                />
              </div>
            )}

            {workflowForm.trigger_type === 'once' && (
              <div className="mb-3">
                <label className="form-label">Run at</label>
                <input
                  type="datetime-local"
                  name="run_at"
                  value={workflowForm.run_at}
                  onChange={handleWorkflowChange}
                  className="form-control"
                  required
                />
              </div>
            )}

            <hr />

            <div className="d-flex justify-content-between align-items-center mb-3">
              <h5 className="mb-0">Workflow steps</h5>
              <button
                type="button"
                className="btn btn-sm btn-outline-primary"
                onClick={addStep}
              >
                Add step
              </button>
            </div>

            <div className="d-flex flex-column gap-3">
              {steps.map((step, index) => (
                <div key={index} className="border rounded p-3">
                  <div className="d-flex justify-content-between align-items-center mb-3">
                    <div>
                      <strong>
                        {index === 0 ? 'Root step' : `Child step ${index}`}
                      </strong>
                    </div>

                    <div className="d-flex gap-2">
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-secondary"
                        onClick={() => moveStepUp(index)}
                        disabled={index === 0}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-secondary"
                        onClick={() => moveStepDown(index)}
                        disabled={index === steps.length - 1}
                      >
                        ↓
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-danger"
                        onClick={() => removeStep(index)}
                        disabled={steps.length === 1}
                      >
                        Remove
                      </button>
                    </div>
                  </div>

                  {index > 0 && (
                    <div className="alert alert-light py-2">
                      Tento krok bude child task a poběží podle rodiče v pořadí kroku.
                    </div>
                  )}

                  <div className="mb-3">
                    <label className="form-label">Step name</label>
                    <input
                      type="text"
                      name="name"
                      value={step.name}
                      onChange={(e) => handleStepChange(index, e)}
                      className="form-control"
                      required
                    />
                  </div>

                  <div className="row">
                    <div className="col-md-6 mb-3">
                      <label className="form-label">VM</label>
                      <select
                        name="vm_id"
                        value={step.vm_id}
                        onChange={(e) => handleStepChange(index, e)}
                        className="form-select"
                        required
                      >
                        <option value="">Select VM</option>
                        {vmOptions.map((vm) => (
                          <option key={`${vm.node_id}-${vm.vm_id}`} value={vm.vm_id}>
                            {vm.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="col-md-6 mb-3">
                      <label className="form-label">Node ID</label>
                      <select
                        name="node_id"
                        value={step.node_id}
                        onChange={(e) => handleStepChange(index, e)}
                        className="form-select"
                        required
                      >
                        <option value="">Select node</option>
                        {nodeOptions.map((node) => (
                          <option key={node.node_id} value={node.node_id}>
                            {node.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="row">
                    <div className="col-md-6 mb-3">
                      <label className="form-label">Action</label>
                      <select
                        name="action"
                        value={step.action}
                        onChange={(e) => handleStepChange(index, e)}
                        className="form-select"
                        required
                      >
                        <option value="start">start</option>
                        <option value="stop">stop</option>
                        <option value="restart">restart</option>
                        <option value="snapshot">snapshot</option>
                      </select>
                    </div>

                    <div className="col-md-6 mb-3">
                      <label className="form-label">Duration seconds</label>
                      <input
                        type="number"
                        min="1"
                        name="duration_seconds"
                        value={step.duration_seconds}
                        onChange={(e) => handleStepChange(index, e)}
                        className="form-control"
                        placeholder="Optional"
                      />
                    </div>
                  </div>

                  {step.action === 'snapshot' && (
                    <div className="mb-3">
                      <label className="form-label">Snapshot name</label>
                      <input
                        type="text"
                        name="snapshot_name"
                        value={step.snapshot_name}
                        onChange={(e) => handleStepChange(index, e)}
                        className="form-control"
                        placeholder="Optional"
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="mt-3">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={submittingWorkflow}
              >
                {submittingWorkflow ? 'Creating workflow...' : 'Create workflow'}
              </button>
            </div>
          </form>
        </div>
      </div>

      <div className="card">
        <div className="card-header">Existing tasks</div>
        <div className="card-body">
          {loading ? (
            <p className="mb-0">Loading tasks...</p>
          ) : tasks.length === 0 ? (
            <p className="mb-0">No automation tasks yet.</p>
          ) : (
            renderTaskList(rootTasks)
          )}
        </div>
      </div>
    </div>
  );
}

export default ServerAutomation;