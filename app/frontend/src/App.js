import React, { useState, useEffect } from 'react';
import Spinner from 'react-bootstrap/Spinner';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import AppNavbar from './layout/Navbar';
import Home from './pages/Home';
import { Container } from 'react-bootstrap';
import Login from './pages/Login';
import { tokenAuth } from './services/UserService';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function checkToken() {
      try {
        await tokenAuth();
        setIsAuthenticated(true);
      } catch (err) {
        console.error("Token auth error:", err);
        setIsAuthenticated(false);
      } finally {
        setLoading(false);
      }
    }

    checkToken();
  }, []);

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center vh-100">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
      </div>
    );
  }

  return (
    <Router>
      <Container fluid className="p-0 m-0 d-flex flex-column vh-100">
        <AppNavbar />

        <div className="flex-grow-1 overflow-y-auto p-2">
          <Routes>
            <Route
              path="/"
              element={
                isAuthenticated
                  ? <Navigate to="/Home" replace />
                  : <Login setIsAuthenticated={setIsAuthenticated} />
              }
            />

            <Route
              path="/Home"
              element={
                isAuthenticated
                  ? <Home />
                  : <Navigate to="/" replace />
              }
            />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </Container>
    </Router>
  );
}

export default App;