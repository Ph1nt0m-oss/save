import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function AuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setUser } = useAuth();
  const hasProcessed = useRef(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processSession = async () => {
      try {
        const hash = location.hash;
        console.log('AuthCallback: Processing hash:', hash);
        
        const sessionIdMatch = hash.match(/session_id=([^&]+)/);
        
        if (!sessionIdMatch) {
          console.error('AuthCallback: No session_id found in hash');
          setError('Aucun session_id trouvé');
          setTimeout(() => navigate('/login'), 2000);
          return;
        }

        const sessionId = sessionIdMatch[1];
        console.log('AuthCallback: Found session_id:', sessionId.substring(0, 10) + '...');

        // Exchange session_id for user data
        const response = await axios.post(
          `${API}/auth/session`,
          { session_id: sessionId },
          { withCredentials: true }
        );

        console.log('AuthCallback: Session created, user:', response.data?.name || response.data?.email);

        // Save session_token to localStorage as fallback when cross-site cookies
        // are blocked by the browser (Brave shields, VPN, Safari ITP, etc.)
        if (response.data?.session_token) {
          try {
            localStorage.setItem('session_token', response.data.session_token);
          } catch (_) {}
        }

        setUser(response.data);
        toast.success('Connexion réussie !');
        
        // Clear hash and navigate to dashboard
        window.history.replaceState(null, '', window.location.pathname);
        navigate('/dashboard', { state: { user: response.data }, replace: true });
      } catch (error) {
        console.error('AuthCallback: Auth error:', error.response?.data || error.message);
        setError(error.response?.data?.detail || 'Erreur d\'authentification');
        toast.error('Erreur de connexion Google. Essayez à nouveau.');
        setTimeout(() => navigate('/login'), 2000);
      }
    };

    processSession();
  }, [location, navigate, setUser]);

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center">
      <div className="text-center">
        {error ? (
          <>
            <div className="w-12 h-12 bg-red-500 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-white text-2xl">!</span>
            </div>
            <p className="text-red-400 font-['IBM_Plex_Sans']">{error}</p>
            <p className="mt-2 text-[#A1A1AA] text-sm">Redirection vers la page de connexion...</p>
          </>
        ) : (
          <>
            <div className="inline-block w-12 h-12 border-4 border-[#E4FF00] border-t-transparent rounded-full animate-spin"></div>
            <p className="mt-4 text-white font-['IBM_Plex_Sans']">Authentification en cours...</p>
          </>
        )}
      </div>
    </div>
  );
}