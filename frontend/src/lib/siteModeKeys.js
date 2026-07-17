/**
 * iter138 — Source unique des 7 clés d'audience/vue utilisées dans les 4
 * onglets créa (SiteModeBadge, WhoCanViewBadge, WhoCanVisitBadge,
 * ViewModePicker). Labels et descriptions IDENTIQUES partout — chaque
 * composant conserve sa propre logique d'écriture.
 *
 * Ordre imposé par l'utilisateur : Privé, Public, Invité, Utilisateurs,
 * Modo, Admin, Créa.
 */
import { Lock, Globe, EyeOff, User, ShieldAlert, ShieldCheck, Crown } from 'lucide-react';

export const SITE_MODE_KEYS = [
  {
    id: 'private', icon: Lock, label: 'Privé',
    hint: 'Seulement les appareils approuvés (sauf le staff)',
  },
  {
    id: 'public', icon: Globe, label: 'Public',
    hint: 'Tout le monde peut accéder au site',
  },
  {
    id: 'guest', icon: EyeOff, label: 'Invité',
    hint: 'Lecture seule pour les appareils ne disposant pas de compte',
  },
  {
    id: 'user', icon: User, label: 'Utilisateurs',
    hint: 'Appareils non approuvés mais possédant un compte validé',
  },
  {
    id: 'modo', icon: ShieldAlert, label: 'Modo',
    hint: 'Modos uniquement',
  },
  {
    id: 'admin', icon: ShieldCheck, label: 'Admin',
    hint: 'Admins uniquement',
  },
  {
    id: 'creator', icon: Crown, label: 'Créa',
    hint: 'Seuls les appareils créateurs',
  },
];

export const SITE_MODE_IDS = SITE_MODE_KEYS.map((k) => k.id);
