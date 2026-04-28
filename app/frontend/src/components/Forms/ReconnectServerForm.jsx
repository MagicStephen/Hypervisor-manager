import { useState } from "react";

function ReconnectServerForm({ server, onSubmit }) {
  const isKvm = server?.platform === "Kvm";

  const [formData, setFormData] = useState({
    password: "",
    mode: isKvm ? "ssh" : null,
  });

  function handleChange(e) {
    const { name, value } = e.target;

    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  }

  function handleSubmit(e) {
    e.preventDefault();

    onSubmit({
      id: server?.id,
      password: formData.password,
      mode: isKvm ? formData.mode : null,
    });
  }

  return (
    <div className="container">
      <p className="text-muted mb-3">
        Your session expired. Please enter your password to reconnect.
      </p>

      <form className="row" onSubmit={handleSubmit}>
        <div className={isKvm ? "mb-3 col-md-6" : "mb-3 col-12"}>
          <label className="form-label">
            <strong>Enter password:</strong>
          </label>
          <input
            type="password"
            name="password"
            className="form-control"
            value={formData.password}
            onChange={handleChange}
            placeholder="Enter your password"
            required
          />
        </div>

        {isKvm && (
          <div className="mb-3 col-md-6">
            <label className="form-label">
              <strong>Mode:</strong>
            </label>
            <select
              name="mode"
              className="form-select"
              value={formData.mode}
              onChange={handleChange}
              required
            >
              <option value="ssh">ssh</option>
              <option value="tls">tls</option>
            </select>
          </div>
        )}

        <div className="col-12 text-end">
          <button type="submit" className="btn btn-primary">
            Reconnect
          </button>
        </div>
      </form>
    </div>
  );
}

export default ReconnectServerForm;