import React, { Suspense, lazy } from 'react';
import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { LanguageProvider } from './contexts/LanguageContext';
import { CacheProvider } from './contexts/CacheContext';
import { Toaster } from './components/ui/sonner';

// Public/auth routes — kept eager (small + on critical path)
import Landing from './pages/Landing';
import Login from './pages/Login';
import SMSLogin from './pages/SMSLogin';
import AuthCallback from './pages/AuthCallback';

// Authenticated/heavy routes — lazy-loaded to shrink initial bundle
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Create = lazy(() => import('./pages/Create'));
const Chat = lazy(() => import('./pages/Chat'));
const GuidedWizard = lazy(() => import('./pages/GuidedWizard'));

// Suspense fallback while a chunk is downloading
const RouteFallback = () => (
  <div data-testid="route-loading" className="min-h-screen bg-[#050505] flex items-center justify-center">
    <div className="text-center">
      <div className="inline-block w-12 h-12 border-4 border-[#E4FF00] border-t-transparent rounded-full animate-spin"></div>
      <p className="mt-4 text-white font-['IBM_Plex_Sans']">Chargement...</p>
    </div>
  </div>
);

// Protected Route wrapper with offline detection
const ProtectedRoute = ({ children, allowOffline = false }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  // If offline mode is allowed, check if we're in offline mode
  if (allowOffline) {
    const isOfflineMode = location.state?.mode === 'offline';
    const isOnline = navigator.onLine;
    
    // If offline mode requested and no internet, allow access without auth
    if (isOfflineMode && !isOnline) {
      return children;
    }
  }

  // If user data was passed from AuthCallback, render immediately
  if (location.state?.user) {
    return children;
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block w-12 h-12 border-4 border-[#E4FF00] border-t-transparent rounded-full animate-spin"></div>
          <p className="mt-4 text-white font-['IBM_Plex_Sans']">Chargement...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

// Router component to handle session_id detection
function AppRouter() {
  const location = useLocation();
  
  // Check URL fragment (not query params) for session_id
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }

  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/sms-login" element={<SMSLogin />} />
        <Route 
          path="/dashboard" 
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/chat" 
          element={
            <ProtectedRoute allowOffline={true}>
              <Chat />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/create" 
          element={
            <ProtectedRoute allowOffline={true}>
              <Create />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/wizard" 
          element={
            <ProtectedRoute allowOffline={true}>
              <GuidedWizard />
            </ProtectedRoute>
          } 
        />
      </Routes>
    </Suspense>
  );
}

function App() {
  return (
    <div className="App dark">
      <BrowserRouter>
        <LanguageProvider>
          <CacheProvider>
            <AuthProvider>
              <AppRouter />
              <Toaster 
                position="top-right"
                theme="dark"
                toastOptions={{
                  style: {
                    background: '#0F0F13',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: '#ffffff',
                  },
                }}
              />
            </AuthProvider>
          </CacheProvider>
        </LanguageProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
