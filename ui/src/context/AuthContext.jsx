import React, { createContext, useState, useEffect, useContext } from 'react';
import * as api from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        checkAuth();
    }, []);

    const checkAuth = async () => {
        const token = localStorage.getItem('token');
        if (!token) {
            setLoading(false);
            return;
        }

        try {
            const userData = await api.getMe();
            setUser(userData);
        } catch (err) {
            console.error('Session expired or invalid', err);
            localStorage.removeItem('token');
            setUser(null);
        } finally {
            setLoading(false);
        }
    };

    const login = async (email, password, rememberMe) => {
        setError(null);
        try {
            const data = await api.login(email, password);
            localStorage.setItem('token', data.access_token);
            // In a real app, rememberMe would affect token expiration or refresh logic
            const userData = await api.getMe();
            setUser(userData);
            return userData;
        } catch (err) {
            setError(err.message);
            throw err;
        }
    };

    const signup = async (email, password, name) => {
        setError(null);
        try {
            await api.signup(email, password, name);
            return await login(email, password);
        } catch (err) {
            setError(err.message);
            throw err;
        }
    };

    const logout = () => {
        localStorage.removeItem('token');
        setUser(null);
        window.location.href = '/login';
    };

    const socialLogin = async (provider, code) => {
        setLoading(true);
        try {
            const data = await api.socialCallback(provider, code);
            localStorage.setItem('token', data.access_token);
            const userData = await api.getMe();
            setUser(userData);
            return userData;
        } catch (err) {
            setError(err.message);
            throw err;
        } finally {
            setLoading(false);
        }
    };

    return (
        <AuthContext.Provider value={{ user, loading, error, login, signup, logout, socialLogin, checkAuth }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
