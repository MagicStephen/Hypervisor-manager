import React, { useEffect, useState } from 'react';
import Spinner from '../Common/Spinner';
import { fetchNodeLogs } from '../../services/NodeService';

function NodeLogs({ serverId, nodeId }) {
  const [nodeLogs, setNodeLogs] = useState([]);
  const [nodeLogsLoading, setNodeLogsLoading] = useState(false);

  async function loadNodeLogs(currentServerId, currentNodeId) {
    try {
      setNodeLogsLoading(true);

      const result = await fetchNodeLogs(currentServerId, currentNodeId);
      setNodeLogs(result?.lines || []);
    } catch (error) {
      console.error('Error loading node logs:', error);
      setNodeLogs([]);
    } finally {
      setNodeLogsLoading(false);
    }
  }

  useEffect(() => {
    if (!serverId || !nodeId) return;
    loadNodeLogs(serverId, nodeId);
  }, [serverId, nodeId]);

  return (
    <div className="col-12 h-100">
      <div className="card h-100 w-100">
        <div className="card-body overflow-auto h-100">
          {nodeLogsLoading ? (
            <Spinner loading={true} />
          ) : nodeLogs.length > 0 ? (
            <pre
              className="mb-0 small"
              style={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                overflowWrap: 'anywhere',
              }}
            >
              {nodeLogs.join('\n')}
            </pre>
          ) : (
            <div className="text-muted">No logs available.</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default NodeLogs;