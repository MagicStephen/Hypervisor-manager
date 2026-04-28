import { useState } from 'react';

function LoginForm({ onSubmit }) {

    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        onSubmit({ username, password });
    };

    return (
        <form className="row" onSubmit={handleSubmit}>
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

export default LoginForm;