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
import VerifyEmail from './pages/VerifyEmail';
import ResetPassword from './pages/ResetPassword';
import HowItWorks from './pages/HowItWorks';
import Legal from './pages/Legal';
import Discover from './pages/Discover';
import FeedbackButton from './components/FeedbackButton';
import SiteLockedOverlay from './components/SiteLockedOverlay';
import ViewModePreviewBanner from './components/ViewModePreviewBanner';
import SessionRequestNotifier from './components/SessionRequestNotifier';
import useDeviceIdentity from './hooks/useDeviceIdentity';

// Global site lock overlay — renders when site is in creator-only mode
// and the current device is not a creator. Sits above every page.
function GlobalSiteLock() {
  const device = useDeviceIdentity();
  // In guest-preview view we suppress the lock so creators / approved devs
  // can preview as a guest would (still read-only via canWrite).
  if (device.viewMode === 'guest') return null;
  return (
    <SiteLockedOverlay
      siteMode={device.siteMode}
      role={device.role}
      kickReason={device.kickReason}
      hasAccount={false}
      onRetry={() => device.refresh()}
    />
  );
}

// Authenticated/heavy routes — lazy-loaded to shrink initial bundle
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Create = lazy(() => import('./pages/Create'));
const Chat = lazy(() => import('./pages/Chat'));
const GuidedWizard = lazy(() => import('./pages/GuidedWizard'));
const Profile = lazy(() => import('./pages/Profile'));
const ProjectPreview = lazy(() => import('./pages/ProjectPreview'));
const SharedPreview = lazy(() => import('./pages/SharedPreview'));

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

// Router component
function AppRouter() {
  // Legacy Google/Emergent OAuth callback (#session_id=...) is no longer
  // supported. If we ever see one (old bookmark / cached link), strip the
  // hash and continue rendering the normal app — the user lands on /login
  // and can sign in with email/password.
  if (typeof window !== 'undefined' && window.location.hash?.includes('session_id=')) {
    try { window.history.replaceState(null, '', window.location.pathname); } catch (_) {}
  }

  return (
    <Suspense fallback={<RouteFallback />}>
      <GlobalSiteLock />
      <ViewModePreviewBanner />
      <SessionRequestNotifier />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/sms-login" element={<SMSLogin />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/how-it-works" element={<HowItWorks />} />
        <Route path="/discover" element={<Discover />} />
        <Route path="/legal" element={<Legal />} />
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
        <Route 
          path="/profile" 
          element={
            <ProtectedRoute>
              <Profile />
            </ProtectedRoute>
          } 
        />
        <Route
          path="/preview/:projectId"
          element={
            <ProtectedRoute>
              <ProjectPreview />
            </ProtectedRoute>
          }
        />
        <Route path="/share/:slug" element={<SharedPreview />} />
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
              <FeedbackButton />
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
