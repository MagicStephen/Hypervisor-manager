import { useState } from 'react';

function AddServerForm({ onSubmit }) {

  const [serverName, setServerName] = useState('');
  const [server, setServer] = useState('');
  const [port, setPort] = useState('');
  const [platform, setPlatform] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({ platform, serverName, host: server, port, username, password });
  };

  return (
    <form className="row" onSubmit={handleSubmit}>
      <div className="mb-3 col-8">
        <label htmlFor="exampleInputEmail1" className="form-label">Server name</label>
        <input
          type="text"
          className="form-control"
          id="exampleInputEmail1"
          value={serverName}
          onChange={e => setServerName(e.target.value)}
        />
      </div>
      <div className="col-4">
        <label htmlFor="exampleInputEmail1" className="form-label">Platform</label>
        <select
          id="platform"
          className="form-select"
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          required
        >
          <option value="">Choose...</option>
          <option value="Proxmox">Proxmox</option>
          <option value="Esxi">Esxi</option>
          <option value="Kvm">KVM</option>
          <option value="Xen">Xen</option>
        </select>
      </div>
      <div className="mb-3 col-9">
        <label htmlFor="exampleInputEmail1" className="form-label">Server address</label>
        <input
          type="text"
          className="form-control"
          id="exampleInputEmail1"
          value={server}
          onChange={e => setServer(e.target.value)}
        />
      </div>
      <div className="col-3">
        <label htmlFor="exampleInputEmail1" className="form-label">Port</label>
        <input
          type="number"
          className="form-control"
          id="exampleInputEmail1"
          value={port}
          onChange={e => setPort(e.target.value)}
        />
      </div>
      <div className="col-12">
        <label htmlFor="exampleInputEmail1" className="form-label">Username</label>
        <input
          type="text"
          className="form-control"
          id="exampleInputEmail1"
          value={username}
          onChange={e => setUsername (e.target.value)}
        />
      </div>
      <div className="mb-3">
        <label htmlFor="exampleInputPassword1" className="form-label">Password</label>
        <input
          type="password"
          className="form-control"
          id="exampleInputPassword1"
          value={password}
          onChange={e => setPassword(e.target.value)}
        />
      </div>

      <button type="submit" className="btn btn-primary">Submit</button>
    </form>
  );
}

export default AddServerForm;