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
  const device = useDeviceIdentity() || {};
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
  const effectiveView = device?.viewMode || device?.role || 'user';
  const viewSpec = spec?.[effectiveView] || spec?.user || {};

  // Override : programming et secret_key_access toujours basés sur role physique
  const isPhysicallyCreator = device?.role === 'creator';

  // iter128 — Buckets de visibilité demandés par l'utilisatrice :
  // - user + guest : aucun outil créa, juste le contenu public.
  // - modo + admin : lecture seule sur les programmations + accès aux comptes
  //   sans les actions "lourdes" (visite, rename, force-visiteur, exclude,
  //   ban, delete) selon le palier.
  // - creator : tout, sauf le contenu des programmations en mode simulation.
  const isStaffOrCreator = ['modo', 'admin', 'creator'].includes(effectiveView);
  const isInvitedOrUser = ['user', 'guest'].includes(effectiveView);
  const isAdminOrCreator = ['admin', 'creator'].includes(effectiveView);

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
    // iter128 — granularité demandée
    canSeeAccountsButton: isStaffOrCreator,
    canSeeMegaphone: isStaffOrCreator,
    canSeeExports: effectiveView === 'creator',
    canSeeIdeasLightbulb: isStaffOrCreator,
    canSeeRobotBots: isStaffOrCreator,
    canSeeAdminProgsCards: isStaffOrCreator,        // Caly + Bots prog cards
    canSeeQuickWizard: isStaffOrCreator,            // "Création rapide accompagnée"
    canSeeCreatorProgsCards: effectiveView === 'creator', // Programmation site/IA
    canEditTestBots: isPhysicallyCreator,           // create/edit/delete bots
    canViewTestBotsCode: isPhysicallyCreator,       // contenu code masqué sinon
    // iter128.1 — Le bouton "Visiter le compte" est restauré pour les
    // APPAREILS CRÉATEUR uniquement (signature ECDSA), pas pour les vues
    // simulées admin/modo/etc.
    canVisitAccountFromList: isPhysicallyCreator,
    canRenameFromAccountsPanel: isAdminOrCreator,   // admin + créa uniquement
    canForceVisitorFromAccountsPanel: isAdminOrCreator,
    canExcludeFromAccountsPanel: isAdminOrCreator,
    canBanFromAccountsPanel: isAdminOrCreator,
    canDeleteFromAccountsPanel: isAdminOrCreator,
    // Profile (actions locales — créa seulement) : rename+mute local
    canLocalRenameMuteInProfile: isPhysicallyCreator,
  };
}
