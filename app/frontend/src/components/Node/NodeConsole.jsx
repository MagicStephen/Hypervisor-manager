import { useState } from 'react';
import SimpleSSHConsole from '../Consoles/sshClient';

function NodeConsole({ serverId, nodeId }) {

  const DEFAULT_SSH_USERNAME = 'root';
  const DEFAULT_SSH_PORT = 22;

  const [formUsername, setFormUsername] = useState(DEFAULT_SSH_USERNAME);
  const [formPassword, setFormPassword] = useState('');
  const [formPort, setFormPort] = useState(DEFAULT_SSH_PORT);

  const [connectionConfig, setConnectionConfig] = useState(null);
  const isConnected = connectionConfig !== null;

  const handleSubmit = (event) => {
    event.preventDefault();

    if (!formUsername || !formPassword) return;

    setConnectionConfig({
      sshUsername: formUsername,
      sshPassword: formPassword,
      sshPort: Number(formPort) || DEFAULT_SSH_PORT
    });
  };

  const handleDisconnect = () => {
    setConnectionConfig(null);
    setFormPassword('');
  };

  return (
    <>
      <div className="col-3 h-100 pe-1">
        <div className="card h-100">
          <div className="card-header">
            <div className="d-flex align-items-center justify-content-between">
              <span>Console</span>
            </div>
          </div>

          <div className="card-body">
            <form onSubmit={handleSubmit}>
              <div className="mb-3">
                <label className="form-label">SSH username</label>
                <input
                  type="text"
                  className="form-control"
                  value={formUsername}
                  onChange={(e) => setFormUsername(e.target.value)}
                  autoComplete="username"
                />
              </div>

              <div className="mb-3">
                <label className="form-label">SSH password</label>
                <input
                  type="password"
                  className="form-control"
                  value={formPassword}
                  onChange={(e) => setFormPassword(e.target.value)}
                  autoComplete="current-password"
                />
              </div>

              <div className="mb-3">
                <label className="form-label">SSH port</label>
                <input
                  type="number"
                  className="form-control"
                  value={formPort}
                  onChange={(e) => setFormPort(e.target.value)}
                  min={1}
                  max={65535}
                />
              </div>

              <button type="submit" className="btn btn-dark btn-sm w-100">
                Connect
              </button>

              {isConnected && (
                <button
                  type="button"
                  className="btn btn-outline-secondary btn-sm w-100 mt-2"
                  onClick={handleDisconnect}
                >
                  Disconnect
                </button>
              )}
            </form>
          </div>
        </div>
      </div>

      <div className="col-9 h-100 ps-1 d-flex">
        {isConnected ? (
          <div className="card h-100 w-100 d-flex flex-column overflow-hidden">
            <div className="card-header">
              <div className="d-flex align-items-center justify-content-between">
                <span>Connection</span>
                <button
                  type="button"
                  className="btn btn-sm btn-outline-secondary"
                  onClick={handleDisconnect}
                >
                  Disconnect
                </button>
              </div>
            </div>

            <div className="flex-grow-1 d-flex overflow-hidden">
              <SimpleSSHConsole
                serverId={serverId}
                nodeId={nodeId}
                sshUsername={connectionConfig.sshUsername}
                sshPassword={connectionConfig.sshPassword}
                sshPort={connectionConfig.sshPort}
              />
            </div>
          </div>
        ) : (
          <div className="card h-100 w-100 d-flex align-items-center justify-content-center text-muted">
            Zadej SSH přihlašovací údaje a připoj se.
          </div>
        )}
      </div>
    </>
  );
}

export default NodeConsole;