import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function SocialCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { socialLogin } = useAuth();
  const [error, setError] = useState('');

  useEffect(() => {
    const code = searchParams.get('code');
    const provider = localStorage.getItem('oauth_provider');

    if (code && provider) {
      handleCallback(provider, code);
    } else {
      setError('Missing authentication code or provider.');
      setTimeout(() => navigate('/login'), 3000);
    }
  }, []);

  const handleCallback = async (provider, code) => {
    try {
      await socialLogin(provider, code);
      localStorage.removeItem('oauth_provider');
      navigate('/wizard');
    } catch (err) {
      setError(err.message || 'Social login failed.');
      setTimeout(() => navigate('/login'), 3000);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100vh', background: '#f8fafc', color: '#1e1b4b' }}>
      {error ? (
        <div style={{ color: '#991b1b', background: '#fee2e2', padding: '1rem 2rem', borderRadius: '8px', border: '1px solid #fecaca' }}>
          {error} Redirecting to login...
        </div>
      ) : (
        <>
          <div className="loading-spinner"></div>
          <p style={{ marginTop: '1.5rem', fontWeight: '500' }}>Completing authentication...</p>
        </>
      )}
    </div>
  );
}
