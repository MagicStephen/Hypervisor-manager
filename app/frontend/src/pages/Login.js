import { useNavigate } from 'react-router-dom';
import LoginForm from '../components/Forms/LoginForm';
import { login } from '../services/UserService';

/**
 * Login stránka aplikace.
 *
 * Zajišťuje:
 * - autentizaci uživatele přes API
 * - uložení autentizačního stavu
 * - přesměrování na hlavní část aplikace
 */
function Login({ setIsAuthenticated }) {

  const navigate = useNavigate();
  
  const handleLogin = ({ username, password }) => {

    login(username, password)
      .then((data) => {

        setIsAuthenticated(true);
        navigate('/servers');
      })
      .catch(err => {
        alert('Špatné přihlašovací údaje');
        console.error('Login error:', err);
      });
  };

  return (
    <div className="d-flex flex-column justify-content-center align-items-center h-100">
      <h1>Virtual Platforms Manager</h1>
      <hr className='w-50'></hr>
      <LoginForm onSubmit={handleLogin} />
    </div>
  );
}

export default Login;