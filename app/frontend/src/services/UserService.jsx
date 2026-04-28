// src/services/authService.js
const API_BASE = process.env.REACT_APP_VPM_API_URL;

export async function login(username, password) {
    
    const res = await fetch(`${API_BASE}/users/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
        credentials: "include"
    });

    if (!res.ok) throw new Error('Login failed');
  
    return res.json();
}

export async function tokenAuth() {
    const res = await fetch(`${API_BASE}/users/token_valid`, {
        method: 'GET',
        credentials: "include"
    });

    if (!res.ok) throw new Error('Token validation failed');
    return res.json();
}