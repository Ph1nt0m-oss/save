/**
 * iter100 — Hook pour consommer la spec des vues du backend.
 * Permet aux composants de masquer/afficher des sections selon le viewMode actif.
 *
 * Usage :
 *   const { canSeeProgramming, canSeeBotsAdmin, visibleChats } = useViewSpec();
 */
import { useEffect, useState } from 'react';
import axios from 'axios';
import useDeviceIdentity from './useDeviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Cache mémoire (la spec ne change quasi jamais)
let _cachedSpec = null;

export default function useViewSpec() {
  const { device } = useDeviceIdentity();
  const [spec, setSpec] = useState(_cachedSpec);

  useEffect(() => {
    if (_cachedSpec) { setSpec(_cachedSpec); return; }
    axios.get(`${API}/views/spec`).then(r => {
      _cachedSpec = r.data;
      setSpec(r.data);
    }).catch(() => { /* silent */ });
  }, []);

  // viewMode prioritaire : si la créatrice simule une vue, on prend la vue simulée.
  // Sauf pour see_programming + secret_key_access : ces 2 restent liés à role
  // physique 'creator' (signature ECDSA), pas à la vue simulée.
  const effectiveView = device.viewMode || device.role || 'user';
  const viewSpec = spec?.[effectiveView] || spec?.user || {};

  // Override : programming et secret_key_access toujours basés sur role physique
  const isPhysicallyCreator = device.role === 'creator';
  return {
    spec,
    viewSpec,
    effectiveView,
    canSeeProgramming: isPhysicallyCreator,  // jamais affecté par la simulation
    canAccessSecretKeys: isPhysicallyCreator,
    canSeeBotsAdmin: !!(viewSpec.see_bots_community),
    canSeeChatbotManagement: !!(viewSpec.see_chatbot_management),
    canSeePollIcon: !!(viewSpec.see_poll_icon),
    canSeeOtherAccountsActions: viewSpec.see_other_accounts_actions || false,
    visibleChats: viewSpec.chats_visible || [],
    hiddenChats: viewSpec.chats_hidden || [],
  };
}
