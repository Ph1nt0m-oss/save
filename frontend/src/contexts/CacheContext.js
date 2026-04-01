import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const CacheContext = createContext();

// Clés de cache
const CACHE_KEYS = {
  PROJECTS: 'codeforge_projects',
  CHAT_HISTORY: 'codeforge_chat_history',
  USER_PREFERENCES: 'codeforge_preferences',
  GENERATED_APPS: 'codeforge_generated_apps',
  OFFLINE_QUEUE: 'codeforge_offline_queue'
};

export function CacheProvider({ children }) {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [offlineQueue, setOfflineQueue] = useState([]);

  // Surveiller la connexion
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      processOfflineQueue();
    };
    
    const handleOffline = () => {
      setIsOnline(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Charger la queue offline au démarrage
    const savedQueue = localStorage.getItem(CACHE_KEYS.OFFLINE_QUEUE);
    if (savedQueue) {
      setOfflineQueue(JSON.parse(savedQueue));
    }

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Sauvegarder dans le cache local
  const saveToCache = useCallback((key, data) => {
    try {
      const cacheItem = {
        data,
        timestamp: Date.now(),
        version: '2.0'
      };
      localStorage.setItem(key, JSON.stringify(cacheItem));
      return true;
    } catch (error) {
      console.error('Cache save error:', error);
      // Si localStorage est plein, nettoyer les anciennes données
      cleanOldCache();
      return false;
    }
  }, []);

  // Lire depuis le cache local
  const getFromCache = useCallback((key, maxAge = 24 * 60 * 60 * 1000) => {
    try {
      const item = localStorage.getItem(key);
      if (!item) return null;

      const { data, timestamp, version } = JSON.parse(item);
      
      // Vérifier la version et l'âge
      if (version !== '2.0') return null;
      if (Date.now() - timestamp > maxAge) return null;

      return data;
    } catch (error) {
      console.error('Cache read error:', error);
      return null;
    }
  }, []);

  // Supprimer du cache
  const removeFromCache = useCallback((key) => {
    localStorage.removeItem(key);
  }, []);

  // Nettoyer les vieilles données du cache
  const cleanOldCache = useCallback(() => {
    const keys = Object.keys(localStorage);
    const now = Date.now();
    const maxAge = 7 * 24 * 60 * 60 * 1000; // 7 jours

    keys.forEach(key => {
      if (key.startsWith('codeforge_')) {
        try {
          const item = JSON.parse(localStorage.getItem(key));
          if (item.timestamp && now - item.timestamp > maxAge) {
            localStorage.removeItem(key);
          }
        } catch (e) {
          // Ignorer les erreurs de parsing
        }
      }
    });
  }, []);

  // Sauvegarder les projets
  const cacheProjects = useCallback((projects) => {
    saveToCache(CACHE_KEYS.PROJECTS, projects);
  }, [saveToCache]);

  // Récupérer les projets cachés
  const getCachedProjects = useCallback(() => {
    return getFromCache(CACHE_KEYS.PROJECTS) || [];
  }, [getFromCache]);

  // Sauvegarder l'historique de chat
  const cacheChatHistory = useCallback((projectId, messages) => {
    const history = getFromCache(CACHE_KEYS.CHAT_HISTORY) || {};
    history[projectId] = messages;
    saveToCache(CACHE_KEYS.CHAT_HISTORY, history);
  }, [getFromCache, saveToCache]);

  // Récupérer l'historique de chat
  const getCachedChatHistory = useCallback((projectId) => {
    const history = getFromCache(CACHE_KEYS.CHAT_HISTORY) || {};
    return history[projectId] || [];
  }, [getFromCache]);

  // Sauvegarder une application générée
  const cacheGeneratedApp = useCallback((projectId, appData) => {
    const apps = getFromCache(CACHE_KEYS.GENERATED_APPS) || {};
    apps[projectId] = {
      ...appData,
      cachedAt: Date.now()
    };
    saveToCache(CACHE_KEYS.GENERATED_APPS, apps);
  }, [getFromCache, saveToCache]);

  // Récupérer une application générée
  const getCachedGeneratedApp = useCallback((projectId) => {
    const apps = getFromCache(CACHE_KEYS.GENERATED_APPS) || {};
    return apps[projectId] || null;
  }, [getFromCache]);

  // Ajouter une action à la queue offline
  const addToOfflineQueue = useCallback((action) => {
    const newQueue = [...offlineQueue, { ...action, queuedAt: Date.now() }];
    setOfflineQueue(newQueue);
    localStorage.setItem(CACHE_KEYS.OFFLINE_QUEUE, JSON.stringify(newQueue));
  }, [offlineQueue]);

  // Traiter la queue offline quand on revient en ligne
  const processOfflineQueue = useCallback(async () => {
    const queue = JSON.parse(localStorage.getItem(CACHE_KEYS.OFFLINE_QUEUE) || '[]');
    
    if (queue.length === 0) return;

    console.log(`Processing ${queue.length} offline actions...`);
    
    for (const action of queue) {
      try {
        // Exécuter l'action (à implémenter selon le type)
        console.log('Processing:', action);
        // await executeAction(action);
      } catch (error) {
        console.error('Failed to process offline action:', error);
      }
    }

    // Vider la queue
    setOfflineQueue([]);
    localStorage.removeItem(CACHE_KEYS.OFFLINE_QUEUE);
  }, []);

  // Sauvegarder les préférences utilisateur
  const savePreferences = useCallback((prefs) => {
    saveToCache(CACHE_KEYS.USER_PREFERENCES, prefs);
  }, [saveToCache]);

  // Récupérer les préférences utilisateur
  const getPreferences = useCallback(() => {
    return getFromCache(CACHE_KEYS.USER_PREFERENCES) || {
      theme: 'dark',
      language: 'fr',
      autoSave: true
    };
  }, [getFromCache]);

  // Obtenir la taille totale du cache
  const getCacheSize = useCallback(() => {
    let total = 0;
    Object.keys(localStorage).forEach(key => {
      if (key.startsWith('codeforge_')) {
        total += localStorage.getItem(key).length * 2; // UTF-16 = 2 bytes per char
      }
    });
    return total;
  }, []);

  // Vider tout le cache
  const clearAllCache = useCallback(() => {
    Object.keys(localStorage).forEach(key => {
      if (key.startsWith('codeforge_')) {
        localStorage.removeItem(key);
      }
    });
    setOfflineQueue([]);
  }, []);

  return (
    <CacheContext.Provider value={{
      isOnline,
      offlineQueue,
      saveToCache,
      getFromCache,
      removeFromCache,
      cacheProjects,
      getCachedProjects,
      cacheChatHistory,
      getCachedChatHistory,
      cacheGeneratedApp,
      getCachedGeneratedApp,
      addToOfflineQueue,
      savePreferences,
      getPreferences,
      getCacheSize,
      clearAllCache
    }}>
      {children}
    </CacheContext.Provider>
  );
}

export function useCache() {
  const context = useContext(CacheContext);
  if (!context) {
    throw new Error('useCache must be used within a CacheProvider');
  }
  return context;
}

export default CacheContext;
