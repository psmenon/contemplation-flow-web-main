import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiClient } from '@/apis';

// Types based on backend wire.py
export interface User {
    id: string;
    phone_number: string;
    name: string;
    phone_verified: boolean;
    role: string;
    is_signed_in: boolean;
    last_active_at: string;
    created_at: string;
    updated_at: string;
}

export interface LoginRequest {
    phone_number: string;
    otp?: string;
}

export interface AuthResponse {
    access_token: string;
    refresh_token: string;
    user: User;
}

export interface SuccessResponse {
    success: boolean;
    message: string;
    data?: any;
}

export interface NewUserRequest {
    phone_number: string;
    name: string;
}

interface AuthContextType {
    user: User | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    login: (phoneNumber: string, otp?: string) => Promise<AuthResponse | SuccessResponse>;
    register: (phoneNumber: string, name: string) => Promise<SuccessResponse>;
    logout: () => Promise<void>;
    checkAuth: () => Promise<boolean>;
    refreshToken: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

interface AuthProviderProps {
    children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const isAuthenticated = !!user && !!localStorage.getItem('accessToken');

    // Check if user is authenticated on app load
    useEffect(() => {
        checkAuth();
    }, []);

    // Set up automatic token refresh
    useEffect(() => {
        const refreshInterval = setInterval(() => {
            if (isAuthenticated) {
                refreshToken();
            }
        }, 50 * 60 * 1000); // Refresh every 50 minutes (tokens expire in 1 hour)

        return () => clearInterval(refreshInterval);
    }, [isAuthenticated]);

    const login = async (phoneNumber: string, otp?: string): Promise<AuthResponse | SuccessResponse> => {
        try {
            const response = await apiClient.post<AuthResponse | SuccessResponse>('/auth/login', {
                phone_number: phoneNumber,
                otp,
            });

            // If this is step 2 (OTP verification) and login successful
            if ('access_token' in response.data) {
                const authResponse = response.data as AuthResponse;
                localStorage.setItem('accessToken', authResponse.access_token);
                localStorage.setItem('refreshToken', authResponse.refresh_token);
                setUser(authResponse.user);
            }

            return response.data;
        } catch (error: any) {
            console.error('Login error:', error);
            throw new Error(error.response?.data?.detail || 'Login failed');
        }
    };

    const register = async (phoneNumber: string, name: string): Promise<SuccessResponse> => {
        try {
            const response = await apiClient.post<SuccessResponse>('/auth/register', {
                phone_number: phoneNumber,
                name,
            });

            return response.data;
        } catch (error: any) {
            console.error('Registration error:', error);
            throw new Error(error.response?.data?.detail || 'Registration failed');
        }
    };

    const logout = async (): Promise<void> => {
        try {
            await apiClient.post('/auth/logout');
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            // Clear tokens and user state regardless of API call success
            localStorage.removeItem('accessToken');
            localStorage.removeItem('refreshToken');
            setUser(null);
        }
    };

    const checkAuth = async (): Promise<boolean> => {
        const token = localStorage.getItem('accessToken');

        if (!token) {
            setIsLoading(false);
            return false;
        }

        try {
            // Check if token is valid by calling /auth/me
            const response = await apiClient.get<User>('/auth/me');
            setUser(response.data);
            setIsLoading(false);
            return true;
        } catch (error: any) {
            console.error('Auth check failed:', error);

            // Token might be expired, try to refresh
            if (error.response?.status === 401) {
                const refreshSuccess = await refreshToken();
                if (refreshSuccess) {
                    return await checkAuth(); // Retry after refresh
                }
            }

            // Clear invalid tokens
            localStorage.removeItem('accessToken');
            localStorage.removeItem('refreshToken');
            setUser(null);
            setIsLoading(false);
            return false;
        }
    };

    const refreshToken = async (): Promise<boolean> => {
        const refreshTokenValue = localStorage.getItem('refreshToken');

        if (!refreshTokenValue) {
            return false;
        }

        try {
            const response = await apiClient.post<AuthResponse>('/auth/refresh', {
                refresh_token: refreshTokenValue,
            });

            localStorage.setItem('accessToken', response.data.access_token);
            localStorage.setItem('refreshToken', response.data.refresh_token);
            setUser(response.data.user);
            return true;
        } catch (error) {
            console.error('Token refresh failed:', error);
            localStorage.removeItem('accessToken');
            localStorage.removeItem('refreshToken');
            setUser(null);
            return false;
        }
    };

    const value: AuthContextType = {
        user,
        isAuthenticated,
        isLoading,
        login,
        register,
        logout,
        checkAuth,
        refreshToken,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}; 