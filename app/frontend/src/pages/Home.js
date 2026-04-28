import React, { useCallback, useEffect, useState } from 'react';

import Modal from '../components/Common/Modal';
import AddServerForm from '../components/Forms/AddServerForm';
import ReconnectServerForm from '../components/Forms/ReconnectServerForm';
import InfrastructureSidebar from '../components/Infrastructure/InfrastructureSidebar';

import NodeDetail from '../components/Node/NodeDetail';
import VmDetail from '../components/Vm/VmDetail';
import ServerDetail from '../components/Server/ServerDetail';

import { serverConnect, serverReconnect, fetchServers } from '../services/ServerService';
import { DropVm } from '../services/VmService';

import { mapServer } from '../utils/infrastructure/mappers';
import { normalizeSelectedItem } from '../utils/infrastructure/normalizers';

const MODAL_MODE = {
  ADD_SERVER: 'Add Server',
  RECONNECT: 'Reconnect'
};

/**
 * Home page – hlavní kontejner pro správu infrastruktury.
 *
 * Zodpovědnosti:
 * - načítání serverů z API
 * - správa stromové struktury (server → cluster → node → VM)
 * - řízení modálních oken (přidání / reconnect serveru)
 * - výběr a zobrazení detailu entity
 */
function Home() {
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState(null);

  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState(null);

  const closeModal = () => {
    setShowModal(false);
    setModalMode(null);
  };

  const openModal = (mode) => {
    setModalMode(mode);
    setShowModal(true);
  };

  /**
   * Načte seznam serverů z backendu a transformuje je do frontend modelu.
   */
  const loadServers = useCallback(async () => {
    try {
      setLoading(true);

      const data = await fetchServers();
      setServers(data.map(mapServer));
    } catch (err) {
      console.error('Error fetching server list:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadServers();
  }, [loadServers]);

  const toggleServer = (serverId) => {
    setServers((prev) =>
      prev.map((server) =>
        server.id === serverId
          ? { ...server, expanded: !server.expanded }
          : server
      )
    );
  };

  const toggleCluster = (serverId, clusterId) => {
    setServers((prev) =>
      prev.map((server) => {
        if (server.id !== serverId) return server;

        return {
          ...server,
          clusters: server.clusters.map((cluster) =>
            cluster.id === clusterId
              ? { ...cluster, expanded: !cluster.expanded }
              : cluster
          )
        };
      })
    );
  };

  const toggleNode = (serverId, clusterId, nodeId) => {
    setServers((prev) =>
      prev.map((server) => {
        if (server.id !== serverId) return server;

        return {
          ...server,
          clusters: server.clusters.map((cluster) => {
            if (cluster.id !== clusterId) return cluster;

            return {
              ...cluster,
              nodes: cluster.nodes.map((node) =>
                node.id === nodeId
                  ? { ...node, expanded: !node.expanded }
                  : node
              )
            };
          })
        };
      })
    );
  };
  
  /**
   * Zpracuje kliknutí na položku ve stromu infrastruktury.
   * - nastaví selectedItem
   * - řeší toggle (server/cluster)
   * - případně otevře reconnect modal
   */
  const handleSelectItem = (item) => {
    const normalizedItem = normalizeSelectedItem(item);
    setSelectedItem(normalizedItem);

    if (item.type === 'server') {
      if (!item.connected) {
        openModal(MODAL_MODE.RECONNECT);
        return;
      }

      toggleServer(item.id);
      return;
    }

    if (item.type === 'cluster') {
      toggleCluster(item.serverId, item.id);
    }
  };

  const handleDropVm = async (vmItem) => {
    if (!vmItem?.serverId || !vmItem?.nodeId || !vmItem?.id) {
      console.error('Missing VM identifiers', vmItem);
      return false;
    }

    try {
      await DropVm(vmItem.serverId, vmItem.nodeId, vmItem.id);
      await loadServers();

      setSelectedItem(null);
      return true;
    } catch (error) {
      console.error('Error deleting VM:', error);
      return false;
    }
  };

  const handleAddServer = async ({
    platform,
    serverName,
    username,
    password,
    host,
    port
  }) => {
    try {
      const fullHost = port ? `${host}:${port}` : host;

      const result = await serverConnect(platform, {
        servername: serverName,
        host: fullHost,
        username,
        password
      });

      if (!result.success) {
        console.error('Nepodařilo se přidat server.');
        return;
      }

      const newServer = mapServer({
        server_id: result.server_id ?? Date.now(),
        name: serverName,
        host: fullHost,
        platform,
        username,
        connected: true,
        clusters: result.clusters || []
      });

      setServers((prev) => [newServer, ...prev]);
      setSelectedItem(normalizeSelectedItem(newServer));
    } catch (err) {
      console.error('Error adding server:', err);
    } finally {
      closeModal();
    }
  };

  const handleReconnectServer = async ({ id, password, mode }) => {
    try {
      const result = await serverReconnect(id, password, mode);
      const currentServer = servers.find((server) => server.id === id);

      if (!currentServer) {
        console.error('Server for reconnect not found in state.');
        return;
      }

      const reconnectedServer = {
        ...mapServer({
          server_id: currentServer.id,
          name: currentServer.name,
          host: currentServer.host,
          platform: currentServer.platform,
          username: currentServer.username,
          connected: true,
          clusters: result.clusters || []
        }),
        expanded: true
      };

      setServers((prev) =>
        prev.map((server) =>
          server.id === id ? reconnectedServer : server
        )
      );

      setSelectedItem(normalizeSelectedItem(reconnectedServer));
    } catch (err) {
      console.error('Error reconnecting server:', err);
    } finally {
      closeModal();
    }
  };

  const renderDetail = () => {
    if (selectedItem?.type === 'server') {
      return (
        <ServerDetail
          selectedItem={selectedItem}
          onRefreshServers={loadServers}
        />
      );
    }

    if (selectedItem?.type === 'node') {
      return (
        <div className="flex-grow-1 ps-3">
          <NodeDetail selectedItem={selectedItem} />
        </div>
      );
    }

    if (selectedItem?.type === 'vm' || selectedItem?.type === 'template') {
      return (
        <div className="flex-grow-1 ps-3">
          <VmDetail
            selectedItem={selectedItem}
            onDeleteVm={handleDropVm}
          />
        </div>
      );
    }

    return null;
  };

  return (
    <div className="d-flex w-100 h-100">
      <InfrastructureSidebar
        servers={servers}
        loading={loading}
        selectedItem={selectedItem}
        onSelect={handleSelectItem}
        onToggleServer={toggleServer}
        onToggleCluster={toggleCluster}
        onToggleNode={toggleNode}
        onAddServer={() => openModal(MODAL_MODE.ADD_SERVER)}
      />

      {renderDetail()}

      <Modal
        title={modalMode}
        show={showModal}
        onClose={closeModal}
        backgroundColor="white"
        color="black"
      >
        {modalMode === MODAL_MODE.RECONNECT && (
          <ReconnectServerForm
            server={{
              id: selectedItem?.id,
              platform: selectedItem?.platform
            }}
            onSubmit={handleReconnectServer}
          />
        )}

        {modalMode === MODAL_MODE.ADD_SERVER && (
          <AddServerForm onSubmit={handleAddServer} />
        )}
      </Modal>
    </div>
  );
}

export default Home;