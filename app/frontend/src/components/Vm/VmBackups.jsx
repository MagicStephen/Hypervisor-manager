import React, { useEffect, useState } from 'react';
import Spinner from '../Common/Spinner';
import { GetVmBackups, CreateVmBackup } from '../../services/VmService';
import { formatBytes, formatDateTimeSafe } from '../../utils/metrics/formatters';

function VmBackup({ selectedItem }) {
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [backups, setBackups] = useState([]);
  const [error, setError] = useState(null);

  function getBackupFilename(backup) {
    if (backup.name) return backup.name;
    if (backup.filename) return backup.filename;
    if (backup.volid) {
      const parts = backup.volid.split('/');
      return parts[parts.length - 1];
    }
    return '-';
  }

  function getBackupStorage(backup) {
    if (backup.storage) return backup.storage;
    if (backup.storageName) return backup.storageName;
    if (backup.volid && backup.volid.includes(':')) {
      return backup.volid.split(':')[0];
    }
    return '-';
  }

  async function loadBackups(currentServerId, currentNodeId, currentVmId) {
    const response = await GetVmBackups(currentServerId, currentNodeId, currentVmId);

    if (Array.isArray(response)) {
      return response;
    }

    return [];
  }

  async function refreshBackups() {
    if (!selectedItem?.serverId || !selectedItem?.nodeId || !selectedItem?.id) {
      setBackups([]);
      setError(null);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const data = await loadBackups(
        selectedItem.serverId,
        selectedItem.nodeId,
        selectedItem.id
      );

      setBackups(Array.isArray(data) ? data : []);
    } catch (loadError) {
      console.error('VM backups load error:', loadError);
      setBackups([]);
      setError(loadError.message || 'Failed to load backups');
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateBackup() {
    if (!selectedItem?.serverId || !selectedItem?.nodeId || !selectedItem?.id) {
      return;
    }

    try {
      setCreating(true);
      setError(null);

      await CreateVmBackup(
        selectedItem.serverId,
        selectedItem.nodeId,
        selectedItem.id
      );

      await refreshBackups();
    } catch (createError) {
      console.error('VM backup create error:', createError);
      setError(createError.message || 'Failed to create backup');
    } finally {
      setCreating(false);
    }
  }

  useEffect(() => {
    if (!selectedItem?.serverId || !selectedItem?.nodeId || !selectedItem?.id) {
      setBackups([]);
      setError(null);
      return;
    }

    refreshBackups();
  }, [selectedItem?.serverId, selectedItem?.nodeId, selectedItem?.id]);

  return (
    <div className="col-12 h-100 ps-0 pe-0">
      <Spinner loading={loading || creating} />

      <div className="card h-100">
        <div className="card-header d-flex justify-content-between align-items-center">
          <div>
            <strong>VM backups</strong>
          </div>

          <div>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleCreateBackup}
              disabled={
                creating ||
                !selectedItem?.serverId ||
                !selectedItem?.nodeId ||
                !selectedItem?.id
              }
            >
              {creating ? 'Vytvářím backup...' : 'Vytvořit backup'}
            </button>
          </div>
        </div>

        <div className="card-body p-0">
          {error ? (
            <div className="d-flex align-items-center justify-content-center text-danger p-4">
              {error}
            </div>
          ) : backups.length === 0 ? (
            <div className="d-flex align-items-center justify-content-center text-muted p-4">
              Pro tuto VM nejsou dostupné žádné backupy.
            </div>
          ) : (
            <div className="table-responsive p-2">
              <table className="table table-hover mb-0 align-middle">
                <thead>
                  <tr>
                    <th>Název souboru</th>
                    <th>Velikost</th>
                    <th>Vytvořeno</th>
                    <th>Storage</th>
                    <th>Typ</th>
                  </tr>
                </thead>
                <tbody>
                  {backups.map((backup, index) => (
                    <tr key={backup.volid || index}>
                      <td>{getBackupFilename(backup)}</td>
                      <td>{formatBytes(backup.size, 2, 'auto')}</td>
                      <td>{formatDateTimeSafe(backup.ctime)}</td>
                      <td>{getBackupStorage(backup)}</td>
                      <td>{backup.subtype || backup.content || 'backup'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default VmBackup;