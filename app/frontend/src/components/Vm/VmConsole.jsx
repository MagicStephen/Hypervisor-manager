import React, { useEffect, useRef, useState } from 'react';
import Spinner from '../Common/Spinner';
import { GetVmConsole } from '../../services/VmService';

import { createVncClient } from '../Consoles/vncClient';
import { createWebMksClient } from '../Consoles/webmksClient';

function VmConsole({ selectedItem, preferredProtocol = 'vnc' }) {
  const [loading, setLoading] = useState(false);
  const [consoleInfo, setConsoleInfo] = useState(null);
  const [error, setError] = useState(null);

  const viewportRef = useRef(null);
  const containerRef = useRef(null);
  const connectionRef = useRef(null);

  async function loadConsole(currentServerId, currentNodeId, currentVmId, protocol) {
    const result = await GetVmConsole(
      currentServerId,
      currentNodeId,
      currentVmId,
      protocol
    );


    return result;
  }

  async function cleanupConnection() {
    if (!connectionRef.current) {
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
      return;
    }

    try {
      if (typeof connectionRef.current.disconnect === 'function') {
        await connectionRef.current.disconnect();
      } else if (typeof connectionRef.current.destroy === 'function') {
        await connectionRef.current.destroy();
      }
    } catch (cleanupError) {
      console.error('Console cleanup error:', cleanupError);
    } finally {
      connectionRef.current = null;

      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    }
  }

  async function connectVnc(info) {
    if (!containerRef.current) return;

    const vncClient = await createVncClient({
      container: containerRef.current,
      wsUrl: info.ws_url,
      password: info.password,
      shared: true,
      viewOnly: false,
      scaleViewport: true,
      resizeSession: false,
      clipViewport: true,
      dragViewport: true,
      background: 'rgb(24, 24, 24)',
      onConnect: () => {
        console.log('VNC connected');
      },
      onDisconnect: (detail) => {
        console.log('VNC disconnected', detail);
      },
      onCredentialsRequired: () => {
        console.warn('VNC credentials required');
      },
      onSecurityFailure: (detail) => {
        console.error('VNC security failure', detail);
      },
      onDesktopName: (name) => {
        console.log('VNC desktop name:', name);
      },
    });

    connectionRef.current = vncClient;
  }

  async function connectWebMks(info) {
    if (!containerRef.current) return;

    const webmksClient = await createWebMksClient({
      container: containerRef.current,
      wsUrl: info.ws_url,
      onConnect: (detail) => {
        console.log('WEBMKS connected', detail);
      },
      onDisconnect: (detail) => {
        console.log('WEBMKS disconnected', detail);
      },
      onError: (detail) => {
        console.error('WEBMKS error', detail);
        setError('WebMKS connection failed');
      }
    });

    connectionRef.current = webmksClient;
  }

  useEffect(() => {
    if (!selectedItem?.serverId || !selectedItem?.nodeId || !selectedItem?.id) {
      setConsoleInfo(null);
      setError(null);
      cleanupConnection();
      return;
    }

    let isMounted = true;

    const initConsole = async () => {
      try {
        setLoading(true);
        setError(null);

        await cleanupConnection();

        const info = await loadConsole(
          selectedItem.serverId,
          selectedItem.nodeId,
          selectedItem.id,
          preferredProtocol
        );

        if (!isMounted) return;

        setConsoleInfo(info);

        if (info.protocol === 'vnc') {
          await connectVnc(info);
        } else if (info.protocol === 'webmks') {
          await connectWebMks(info);
        } else {
          throw new Error(`Unsupported console protocol: ${info.protocol}`);
        }
      } catch (initError) {
        console.error('VM console init error:', initError);

        if (isMounted) {
          setConsoleInfo(null);
          setError(initError.message || 'Failed to initialize console');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    initConsole();

    return () => {
      isMounted = false;
      cleanupConnection();
    };
  }, [selectedItem?.serverId, selectedItem?.nodeId, selectedItem?.id, preferredProtocol]);

  return (
  <div className="col-12 ps-0 pe-0 h-100">
    <Spinner loading={loading} />

    <div className="card h-100 d-flex flex-column">
      <div className="card-header d-flex justify-content-between align-items-center flex-shrink-0">
        <div>
          <strong>VM console</strong>
        </div>

        <div className="text-muted small">
          {consoleInfo?.protocol ? `Protocol: ${consoleInfo.protocol}` : 'Not connected'}
        </div>
      </div>

      <div
        className="card-body px-2 py-0 flex-grow-1"
        style={{
          minHeight: 0,
          overflow: 'hidden',
          backgroundColor: '#181818',
        }}
      >
        {error ? (
          <div className="d-flex align-items-center justify-content-center h-100 text-danger py-0">
            {error}
          </div>
        ) : (
          <div
            ref={viewportRef}
            style={{
              width: '100%',
              height: '100%',
              overflow: 'hidden',
              backgroundColor: '#181818',
            }}
          >
            <div
              ref={containerRef}
              style={{
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'flex-start',
                overflow: 'hidden',
                backgroundColor: '#181818',
                lineHeight: 0,
              }}
            />
          </div>
        )}
      </div>
    </div>
  </div>
);
}

export default VmConsole;