import React, { useEffect, useMemo, useState } from 'react';
import {
  fetchNodeStorage,
  fetchNodeStorageContent,
  deleteNodeStorageContent,
  uploadNodeStorageFile
} from '../../services/NodeService';

import { formatBytes } from '../../utils/metrics/formatters';
import { getUsagePercent } from '../../utils/metrics/calculations';
import { NODE_STORAGE_CONTENT_LABELS } from '../../utils/node/constants';

import Spinner from '../Common/Spinner';
import Modal from '../Common/Modal';

function NodeStorage({ serverId, nodeId, onLoadingChange }) {
  const [storages, setStorages] = useState([]);
  const [selectedStorageId, setSelectedStorageId] = useState(null);
  const [selectedStorageFiles, setSelectedStorageFiles] = useState([]);
  const [activeContentFilter, setActiveContentFilter] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);

  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadContentType, setUploadContentType] = useState('');
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const [loadingFiles, setLoadingFiles] = useState(false);

  const selectedStorage = useMemo(
    () => storages.find((s) => s.storage_id === selectedStorageId) || null,
    [storages, selectedStorageId]
  );

  const selectedStorageContentFilter = selectedStorage?.content || [];
  const selectedStorageContentUploadAllowed = selectedStorage?.upload_allowed || [];

  const filteredStorageFiles = useMemo(() => {
    if (!activeContentFilter) return [];
    return selectedStorageFiles.filter((file) => file.content === activeContentFilter);
  }, [selectedStorageFiles, activeContentFilter]);

  const isUploadAllowed =
    !!selectedStorage &&
    !!activeContentFilter &&
    selectedStorageContentUploadAllowed.includes(activeContentFilter);

  function getContentTypeLabel(type) {
    return NODE_STORAGE_CONTENT_LABELS[type] || type;
  }

  function resetStorageSelection() {
    setSelectedStorageId(null);
    setSelectedStorageFiles([]);
    setActiveContentFilter(null);
    setSelectedFile(null);
  }

  async function loadStorages() {
    onLoadingChange?.(true);
    resetStorageSelection();

    try {
      const result = await fetchNodeStorage(serverId, nodeId);
      setStorages(Array.isArray(result) ? result : []);
    } catch (error) {
      console.error('Error loading node storages:', error);
      setStorages([]);
    } finally {
      onLoadingChange?.(false);
    }
  }

  async function loadStorageContent(storageId) {
    setLoadingFiles(true);
    setSelectedStorageId(storageId);
    setSelectedFile(null);

    try {
      const storage = storages.find((s) => s.storage_id === storageId) || null;
      const availableFilters = storage?.content || [];

      setActiveContentFilter((prev) =>
        prev && availableFilters.includes(prev)
          ? prev
          : availableFilters[0] || null
      );

      const result = await fetchNodeStorageContent(serverId, nodeId, storageId);
      setSelectedStorageFiles(Array.isArray(result) ? result : []);
    } catch (error) {
      console.error('Error loading storage content:', error);
      setSelectedStorageFiles([]);
    } finally {
      setLoadingFiles(false);
    }
  }

  function openUploadModal() {
    if (!selectedStorage) return;

    const defaultUploadType = selectedStorageContentUploadAllowed.includes(activeContentFilter)
      ? activeContentFilter
      : selectedStorageContentUploadAllowed[0] || '';

    setUploadContentType(defaultUploadType);
    setUploadFile(null);
    setUploadProgress(0);
    setShowUploadModal(true);
  }

  function closeUploadModal() {
    if (uploading) return;

    setShowUploadModal(false);
    setUploadFile(null);
    setUploadProgress(0);
  }

  async function handleDeleteFile() {
    if (!selectedStorageId || !selectedFile) return;

    const fileLabel = selectedFile.includes('/')
      ? selectedFile.split('/').slice(1).join('/')
      : selectedFile;

    const confirmed = window.confirm(`Opravdu chceš smazat soubor "${fileLabel}"?`);
    if (!confirmed) return;

    try {
      await deleteNodeStorageContent(
        serverId,
        nodeId,
        selectedStorageId,
        selectedFile
      );

      setSelectedFile(null);
      await loadStorageContent(selectedStorageId);
    } catch (error) {
      console.error('Error deleting storage file:', error);
    }
  }

  async function handleUploadFile() {
    if (!selectedStorageId || !uploadContentType || !uploadFile) return;

    setUploading(true);
    setUploadProgress(0);

    try {
      await uploadNodeStorageFile(
        serverId,
        nodeId,
        selectedStorageId,
        uploadContentType,
        uploadFile,
        setUploadProgress
      );

      setShowUploadModal(false);
      setUploadFile(null);
      setUploadProgress(0);
      setActiveContentFilter(uploadContentType);

      await loadStorageContent(selectedStorageId);
    } catch (error) {
      console.error('Error uploading storage file:', error);
    } finally {
      setUploading(false);
    }
  }

  useEffect(() => {
    if (serverId == null || nodeId == null) {
      setStorages([]);
      resetStorageSelection();
      return;
    }

    loadStorages();
  }, [serverId, nodeId]);

  return (
    <>
      <div className="col-3 h-100 pe-1">
        <div className="card h-100">
          <div className="card-header">
            <div className="d-flex align-items-center justify-content-between">
              <span>Storages</span>
            </div>
          </div>

          {storages.length === 0 ? (
            <div className="card-body text-muted">
              Žádné storage nejsou k dispozici.
            </div>
          ) : (
            <div className="card-body h-100 p-2 overflow-y-auto">
              <div className="col-12 p-0 h-100">
                <div className="list-group">
                  {storages.map((storage) => {
                    const total = Number(storage.total) || 0;
                    const used = Number(storage.used) || 0;
                    const percent = getUsagePercent(total, used);
                    const storageName = storage.storage;
                    const storageId = storage.storage_id;

                    return (
                      <button
                        key={storageId}
                        type="button"
                        className={`list-group-item list-group-item-action ${
                          selectedStorageId === storageId ? 'active' : ''
                        }`}
                        onClick={() => loadStorageContent(storageId)}
                      >
                        <div className="d-flex justify-content-between align-items-center mb-2">
                          <div>
                            <strong>{storageName}</strong>
                            <div className="small text-muted">
                              {storage.type || '-'}
                            </div>
                          </div>

                          <div className="small text-end">
                            {formatBytes(used, 2, 'auto')} / {formatBytes(total, 2, 'auto')}
                          </div>
                        </div>

                        <div className="progress" style={{ height: '8px' }}>
                          <div
                            className="progress-bar bg-secondary"
                            style={{ width: `${percent}%` }}
                          />
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="col-9 ps-1 h-100">
        <div className="card h-100 d-flex flex-column">
          <div className="card-header p-2">
            <div className="ps-2 align-items-center justify-content-end d-flex">
              <button
                className="btn btn-sm btn-outline-primary"
                onClick={openUploadModal}
                disabled={!isUploadAllowed}
              >
                Upload
              </button>

              <button
                className="btn btn-sm btn-outline-danger ms-2"
                onClick={handleDeleteFile}
                disabled={!selectedFile}
              >
                Delete
              </button>
            </div>
          </div>

          <div
            className="card-body p-0 flex-grow-1 d-flex flex-row position-relative"
            style={{ minHeight: 0 }}
          >
            {loadingFiles && <Spinner loading={loadingFiles} />}

            {selectedStorageContentFilter.length > 0 && (
              <div className="p-2 border-bottom d-flex flex-column gap-2 card rounded-0 border-top-0 border-bottom-0 border-start-0 w-25">
                {[...selectedStorageContentFilter]
                  .sort((a, b) =>
                    getContentTypeLabel(a).localeCompare(getContentTypeLabel(b))
                  )
                  .map((contentType) => (
                    <button
                      key={contentType}
                      type="button"
                      className={`btn btn-sm ${
                        activeContentFilter === contentType
                          ? 'btn-primary'
                          : 'btn-outline-secondary'
                      }`}
                      onClick={() => {
                        setActiveContentFilter(contentType);
                        setSelectedFile(null);
                      }}
                    >
                      {getContentTypeLabel(contentType)}
                    </button>
                  ))}
              </div>
            )}

            {selectedStorageId !== null &&
              !loadingFiles &&
              selectedStorageFiles.length === 0 && (
                <div className="d-flex text-muted align-items-center justify-content-center w-75 h-100">
                  Storage is empty.
                </div>
              )}

            {selectedStorageId !== null &&
              !loadingFiles &&
              selectedStorageFiles.length > 0 &&
              activeContentFilter !== null &&
              filteredStorageFiles.length === 0 && (
                <div className="d-flex text-muted align-items-center justify-content-center w-75 h-100">
                  Pro zvolený typ obsahu zde nejsou žádné soubory.
                </div>
              )}

            {selectedStorageFiles.length > 0 &&
              activeContentFilter !== null &&
              filteredStorageFiles.length > 0 && (
                <div className="overflow-y-auto d-flex w-75">
                  <table className="table align-middle mb-0 align-self-start w-100">
                    <thead className="sticky-top bg-white">
                      <tr>
                        <th>Name</th>
                        <th>Content</th>
                        <th>Size</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredStorageFiles.map((file) => (
                        <tr
                          key={file.volid}
                          onClick={() => setSelectedFile(file.volid)}
                          className={selectedFile === file.volid ? 'table-active' : ''}
                          style={{ cursor: 'pointer' }}
                        >
                          <td>{file.name}</td>
                          <td>{file.content || '-'}</td>
                          <td>{formatBytes(file.size, 2, 'auto')}</td>
                          <td className="text-end"></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
          </div>
        </div>
      </div>

      {showUploadModal && (
        <Modal
          show={showUploadModal}
          title="Upload souboru"
          onClose={closeUploadModal}
        >
          <div className="mb-3">
            <label className="form-label">Content typ</label>
            <select
              className="form-select"
              value={uploadContentType}
              onChange={(e) => setUploadContentType(e.target.value)}
              disabled={uploading}
            >
              <option value="">Vyber content typ</option>
              {selectedStorageContentUploadAllowed.map((type) => (
                <option key={type} value={type}>
                  {getContentTypeLabel(type)}
                </option>
              ))}
            </select>
          </div>

          <div className="mb-3">
            <label className="form-label">Soubor</label>
            <input
              type="file"
              className="form-control"
              onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
              disabled={uploading}
            />
          </div>

          {uploadFile && (
            <div className="small text-muted mb-3">
              Vybraný soubor: <strong>{uploadFile.name}</strong>
            </div>
          )}

          {uploading && (
            <div className="mb-3">
              <label className="form-label">Nahrávání souboru...</label>
              <div className="progress">
                <div
                  className="progress-bar progress-bar-striped progress-bar-animated"
                  role="progressbar"
                  style={{ width: `${uploadProgress}%` }}
                  aria-valuenow={uploadProgress}
                  aria-valuemin="0"
                  aria-valuemax="100"
                >
                  {uploadProgress}%
                </div>
              </div>
            </div>
          )}

          <div className="d-flex justify-content-end gap-2">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={closeUploadModal}
              disabled={uploading}
            >
              Zavřít
            </button>

            <button
              type="button"
              className="btn btn-primary"
              onClick={handleUploadFile}
              disabled={!uploadContentType || !uploadFile || uploading}
            >
              {uploading ? 'Nahrávám...' : 'Nahrát'}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

export default NodeStorage;