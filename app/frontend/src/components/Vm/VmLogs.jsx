import React, { useEffect, useMemo, useState } from 'react';
import Spinner from '../Common/Spinner';
import { fetchVmLogs } from '../../services/VmService';

function formatStartTime(starttime) {
  if (!starttime) return '';

  return new Date(starttime * 1000).toLocaleString('cs-CZ', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function VmLogs({ selectedItem, limit = 1000 }) {
  const [loading, setLoading] = useState(false);
  const [lines, setLines] = useState([]);
  const [linesCount, setLinesCount] = useState(0);
  const [error, setError] = useState(null);

  const isValidVm = Boolean(
    selectedItem?.type === 'vm' &&
    selectedItem?.serverId &&
    selectedItem?.id
  );

  const logEntries = useMemo(() => {
    return Array.isArray(lines) ? lines : [];
  }, [lines]);

  useEffect(() => {
    if (!isValidVm) {
      setLines([]);
      setLinesCount(0);
      setError(null);
      return;
    }

    let isMounted = true;

    async function loadLogs() {
      try {
        setLoading(true);
        setError(null);

        const result = await fetchVmLogs(
          selectedItem.serverId,
          selectedItem.nodeId,
          selectedItem.id,
          limit
        );

        console.log('VM logs result:', result);

        if (!isMounted) return;

        setLines(Array.isArray(result?.lines) ? result.lines : []);
        setLinesCount(result?.lines_count || 0);
      } catch (err) {
        console.error('Error loading VM logs:', err);

        if (!isMounted) return;

        setLines([]);
        setLinesCount(0);
        setError(err?.message || 'Failed to load VM logs');
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadLogs();

    return () => {
      isMounted = false;
    };
  }, [
    selectedItem?.serverId,
    selectedItem?.nodeId,
    selectedItem?.id,
    selectedItem?.type,
    isValidVm,
    limit
  ]);

  return (
    <div className="col-12 ps-0 pe-0 h-100">
      <Spinner loading={loading} />

      <div className="card h-100">
        <div className="card-header py-2 px-3 d-flex justify-content-between align-items-center">
          <strong>VM logs</strong>
          <span className="text-muted small">
            {linesCount} lines
          </span>
        </div>

        <div
          className="card-body px-3 py-2"
          style={{
            overflowY: 'auto',
            background: '#111',
            color: '#f1f1f1',
            fontFamily: 'monospace',
            fontSize: '12px',
            whiteSpace: 'pre-wrap',
          }}
        >
          {error ? (
            <div style={{ color: '#ff6b6b' }}>{error}</div>
          ) : !loading && logEntries.length === 0 ? (
            <div style={{ color: '#bdbdbd' }}>No logs found for this VM.</div>
          ) : (
            logEntries.map((entry, index) => (
              <div
                key={`${entry?.upid || 'log'}-${entry?.line_no ?? index}`}
                className="mb-1"
              >
                <span style={{ color: '#81c995' }}>
                  {formatStartTime(entry?.starttime)}
                </span>{' '}

                <span style={{ color: '#8ab4f8' }}>
                  [{entry?.type ?? 'unknown'}]
                </span>{' '}

                <span style={{ color: '#f1f1f1' }}>
                  {entry?.text ?? ''}
                </span>

                {entry?.status && (
                  <span style={{ color: '#bdbdbd' }}>
                    {' '}({entry.status})
                  </span>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default VmLogs;