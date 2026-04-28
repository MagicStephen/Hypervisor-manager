import React, { useEffect, useMemo, useState } from 'react';
import Spinner from '../Common/Spinner';
import {
  GetVmSnapshots,
  CreateVmSnapshot,
  DropVmSnapshot,
  RollbackVmSnapshot
} from '../../services/VmService';

function formatSnapshotDate(value) {
  if (!value) return '-';

  const timestamp = Number(value);

  if (!Number.isNaN(timestamp)) {
    const date = new Date(timestamp * 1000);
    if (!Number.isNaN(date.getTime())) {
      return date.toLocaleString('cs-CZ');
    }
  }

  const date = new Date(value);
  if (!Number.isNaN(date.getTime())) {
    return date.toLocaleString('cs-CZ');
  }

  return String(value);
}

function getSnapshotTime(value) {
  if (!value) return 0;

  const timestamp = Number(value);
  if (!Number.isNaN(timestamp)) {
    return timestamp;
  }

  const date = new Date(value);
  if (!Number.isNaN(date.getTime())) {
    return date.getTime();
  }

  return 0;
}

function isCurrentSnapshot(snapshot) {
  return (
    snapshot?.is_current === true ||
    snapshot?.name === 'current' ||
    snapshot?.running === 1 ||
    snapshot?.running === true
  );
}

function VmSnapshots({ selectedItem }) {
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const [saveVmState, setSaveVmState] = useState(true);

  const [selectedSnapshotId, setSelectedSnapshotId] = useState('');
  const [newSnapshotName, setNewSnapshotName] = useState('');
  const [newSnapshotDescription, setNewSnapshotDescription] = useState('');

  const [message, setMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const isValidVm =
    selectedItem?.serverId &&
    selectedItem?.nodeId &&
    selectedItem?.id;

  async function loadSnapshots() {
    if (!isValidVm) {
      setSnapshots([]);
      return;
    }

    try {
      setLoading(true);
      setErrorMessage('');
      setMessage('');

      const result = await GetVmSnapshots(
        selectedItem.serverId,
        selectedItem.nodeId,
        selectedItem.id
      );

      const data = Array.isArray(result) ? result : [];
      setSnapshots(data);
    } catch (error) {
      console.error('Error loading VM snapshots:', error);
      setSnapshots([]);
      setErrorMessage('Došlo k chybě při načítání snapshotů.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setSelectedSnapshotId('');
    loadSnapshots();
  }, [selectedItem]);

  const selectedSnapshot = useMemo(() => {
    return snapshots.find((item) => item.id === selectedSnapshotId) || null;
  }, [snapshots, selectedSnapshotId]);

  const currentSnapshot = useMemo(() => {
    return snapshots.find((snapshot) => isCurrentSnapshot(snapshot)) || null;
  }, [snapshots]);

  const visibleSnapshots = useMemo(() => {
    return snapshots
      .filter((snapshot) => !isCurrentSnapshot(snapshot))
      .sort((a, b) => getSnapshotTime(b?.snaptime) - getSnapshotTime(a?.snaptime));
  }, [snapshots]);

  const selectedIsCurrent = isCurrentSnapshot(selectedSnapshot);

  const canDelete = !!selectedSnapshot && !selectedIsCurrent && !actionLoading;
  const canRollback = !!selectedSnapshot && !selectedIsCurrent && !actionLoading;

  async function handleCreateSnapshot() {
    if (!newSnapshotName.trim()) {
      setErrorMessage('Zadej název snapshotu.');
      return;
    }

    try {
      setActionLoading(true);
      setErrorMessage('');
      setMessage('');

      await CreateVmSnapshot(
        selectedItem.serverId,
        selectedItem.nodeId,
        selectedItem.id,
        {
          snapname: newSnapshotName.trim(),
          description: newSnapshotDescription.trim(),
          vmstate: saveVmState ? 1 : 0
        }
      );

      setMessage('Snapshot byl vytvořen.');
      setNewSnapshotName('');
      setNewSnapshotDescription('');
      setSelectedSnapshotId('');
      await loadSnapshots();
    } catch (error) {
      console.error('Error creating snapshot:', error);
      setErrorMessage('Došlo k chybě při vytváření snapshotu.');
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDeleteSnapshot() {
    if (!selectedSnapshot || selectedIsCurrent) return;

    try {
      setActionLoading(true);
      setErrorMessage('');
      setMessage('');

      await DropVmSnapshot(
        selectedItem.serverId,
        selectedItem.nodeId,
        selectedItem.id,
        selectedSnapshot.id
      );

      setMessage(`Snapshot "${selectedSnapshot.name}" byl smazán.`);
      setSelectedSnapshotId('');
      await loadSnapshots();
    } catch (error) {
      console.error('Error deleting snapshot:', error);
      setErrorMessage('Došlo k chybě při mazání snapshotu.');
    } finally {
      setActionLoading(false);
    }
  }

  async function handleRollbackSnapshot() {
    if (!selectedSnapshot || selectedIsCurrent) return;

    try {
      setActionLoading(true);
      setErrorMessage('');
      setMessage('');

      await RollbackVmSnapshot(
        selectedItem.serverId,
        selectedItem.nodeId,
        selectedItem.id,
        selectedSnapshot.id
      );

      setMessage(`Rollback na snapshot "${selectedSnapshot.name}" byl spuštěn.`);
      await loadSnapshots();
    } catch (error) {
      console.error('Error rolling back snapshot:', error);
      setErrorMessage('Došlo k chybě při rollbacku snapshotu.');
    } finally {
      setActionLoading(false);
    }
  }

  if (!isValidVm) {
    return (
      <div className="col-12 h-100">
        <div className="card h-100">
          <div className="card-body d-flex align-items-center text-muted">
            Nebyla vybrána žádná VM.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="col-12 h-100">
      <div className="card h-100 d-flex flex-column">
        <div className="card-header p-2">
          <div className="row g-2 align-items-end">
            <div className="col-md-7">
              <div className="border rounded p-2">
                <div className="fw-semibold mb-2">Create snapshot</div>

                <div className="row g-2">
                  <div className="col-md-4">
                    <label className="form-label mb-1">Snapshot name</label>
                    <input
                      type="text"
                      className="form-control form-control-sm"
                      value={newSnapshotName}
                      onChange={(e) => setNewSnapshotName(e.target.value)}
                      placeholder="např. before-update"
                      disabled={actionLoading}
                    />
                  </div>

                  <div className="col-md-5">
                    <label className="form-label mb-1">Description</label>
                    <input
                      type="text"
                      className="form-control form-control-sm"
                      value={newSnapshotDescription}
                      onChange={(e) => setNewSnapshotDescription(e.target.value)}
                      placeholder="volitelný popis"
                      disabled={actionLoading}
                    />
                  </div>
                  <div className="col-md-3">
                    <label className="form-label mb-1 d-block">Options</label>
                    <div className="form-check">
                      <input
                        className="form-check-input"
                        type="checkbox"
                        id="saveVmState"
                        checked={saveVmState}
                        onChange={(e) => setSaveVmState(e.target.checked)}
                        disabled={actionLoading}
                      />
                      <label className="form-check-label" htmlFor="saveVmState">
                        Save VM state
                      </label>
                    </div>
                  </div>
                  <div className='col-9'></div>
                  <div className="col-md-3 d-flex align-items-end">
                    <button
                      className="btn btn-success btn-sm w-100"
                      onClick={handleCreateSnapshot}
                      disabled={actionLoading || !newSnapshotName.trim()}
                    >
                      Create
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div className="col-md-5">
              <div className="border rounded p-2 h-100 d-flex flex-column justify-content-between">
                <div className="small text-muted mb-2">
                  <div>
                    Current snapshot:{' '}
                    <strong>{currentSnapshot?.parent || currentSnapshot?.name || '-'}</strong>
                  </div>

                  <div className="mt-1">
                    Selected snapshot:{' '}
                    <strong>{selectedSnapshot?.name || '-'}</strong>
                  </div>
                </div>

                <div className="d-flex justify-content-end gap-2">
                  <button
                    className="btn btn-outline-danger btn-sm"
                    onClick={handleDeleteSnapshot}
                    disabled={!canDelete}
                  >
                    Delete
                  </button>

                  <button
                    className="btn btn-outline-warning btn-sm"
                    onClick={handleRollbackSnapshot}
                    disabled={!canRollback}
                  >
                    Rollback
                  </button>

                  <button
                    className="btn btn-outline-secondary btn-sm"
                    onClick={loadSnapshots}
                    disabled={loading || actionLoading}
                  >
                    Refresh
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div
          className="card-body p-0 flex-grow-1 position-relative"
          style={{ minHeight: 0 }}
        >
          <Spinner loading={loading || actionLoading} />

          <div className="h-100 overflow-auto p-3 pt-0">
            {message && (
              <div className="alert alert-success py-2" role="alert">
                {message}
              </div>
            )}

            {errorMessage && (
              <div className="alert alert-danger py-2" role="alert">
                {errorMessage}
              </div>
            )}

            {visibleSnapshots.length === 0 ? (
              <div className="text-muted">
                VM has no snapshots.
              </div>
            ) : (
              <div style={{ top: 0 }}>
                <table className="table table-hover align-middle mb-0">
                  <thead style={{ top: 0 }}>
                    <tr>
                      <th style={{ width: '50px', position: 'sticky', top: 0, zIndex: 10, background: 'white' }}></th>
                      <th style={{ position: 'sticky', top: 0, zIndex: 10, background: 'white' }}>Name</th>
                      <th style={{ position: 'sticky', top: 0, zIndex: 2, background: 'white' }}>Description</th>
                      <th style={{ position: 'sticky', top: 0, zIndex: 2, background: 'white' }}>Date</th>
                      <th style={{ position: 'sticky', top: 0, zIndex: 2, background: 'white' }}>Parent</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleSnapshots.map((snapshot) => {
                      const isSelected = selectedSnapshotId === snapshot.id;
                      const isActiveBase = snapshot.id === currentSnapshot?.parent_id;

                      return (
                        <tr
                          key={snapshot.id}
                          className={isSelected ? 'table-active' : ''}
                          style={{
                            cursor: 'pointer',
                            backgroundColor: isActiveBase ? '#f8d7da' : undefined
                          }}
                          onClick={() => setSelectedSnapshotId(snapshot.id)}
                        >
                          <td>
                            <input
                              type="radio"
                              name="selectedSnapshot"
                              checked={isSelected}
                              onChange={() => setSelectedSnapshotId(snapshot.id)}
                            />
                          </td>
                          <td>
                            {snapshot.name || '-'}
                            {isActiveBase && (
                              <span className="badge bg-danger ms-2">Current</span>
                            )}
                          </td>
                          <td>{snapshot.description || '-'}</td>
                          <td>{formatSnapshotDate(snapshot.snaptime)}</td>
                          <td>{snapshot.parent || '-'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default VmSnapshots;