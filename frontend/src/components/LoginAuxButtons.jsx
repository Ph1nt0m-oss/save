/**
 * iter149/150 — LoginAuxButtons : « Visite du compte » + « Choix de vue ».
 *
 * Spec (iter150) :
 *   - Le dropdown "Choix de vue" liste MAINTENANT les 5 vues disponibles
 *     (creator/user/modo/admin/guest), pas juste 2.
 *   - Le libellé du bouton "Choix de vue" reflète la vue actuellement
 *     sélectionnée (ex. « Vue : Utilisateur inscrit »). S'aligne sur
 *     `codeforge_view_mode` en localStorage.
 *   - « Visite du compte » lance la simulation avec la vue courante
 *     (par défaut 'user' si aucune vue n'a été explicitement choisie),
 *     marque le device comme simulation-unauth (spec F : redirection
 *     vers /login quand la vue est décochée), puis navigue vers /dashboard.
 *
 * Layout : 2 boutons `flex-1` (mêmes largeurs — spec A/B iter149).
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Eye, User, EyeOff, Lock, ChevronDown, Crown, ShieldAlert, ShieldCheck, Check,
} from 'lucide-react';
import { setStoredViewMode, setSimulationUnauth } from '../hooks/useDeviceIdentity';

const VIEW_OPTIONS = [
  { key: 'creator', label: 'Créateur',           short: 'Créa',           Icon: Crown,        color: 'text-[#E4FF00]', desc: 'Vue complète du site (Créa)' },
  { key: 'user',    label: 'Utilisateur inscrit', short: 'Utilisateur',  Icon: User,         color: 'text-lime-300',  desc: 'Vue d\'un utilisateur connecté' },
  { key: 'modo',    label: 'Modérateur',         short: 'Modo',          Icon: ShieldAlert,  color: 'text-cyan-300',  desc: 'Vue d\'un modérateur' },
  { key: 'admin',   label: 'Administrateur',     short: 'Admin',         Icon: ShieldCheck,  color: 'text-orange-300', desc: 'Vue d\'un administrateur' },
  { key: 'guest',   label: 'Invité (lecture seule)', short: 'Invité',    Icon: EyeOff,       color: 'text-violet-300', desc: 'Vue sans compte, aucune donnée écrite' },
];

const VIEW_MODE_KEY = 'codeforge_view_mode';

export default function LoginAuxButtons() {
  const navigate = useNavigate();
  const [viewOpen, setViewOpen] = useState(false);
  const [selectedView, setSelectedView] = useState(() => {
    try { return localStorage.getItem(VIEW_MODE_KEY) || ''; }
    catch (_) { return ''; }
  });
  const wrapRef = useRef(null);

  // Sync avec toute autre place qui modifierait codeforge_view_mode.
  useEffect(() => {
    const sync = () => {
      try { setSelectedView(localStorage.getItem(VIEW_MODE_KEY) || ''); }
      catch (_) { setSelectedView(''); }
    };
    window.addEventListener('codeforge:view-mode-changed', sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener('codeforge:view-mode-changed', sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  useEffect(() => {
    if (!viewOpen) return undefined;
    const onDown = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setViewOpen(false);
    };
    window.addEventListener('mousedown', onDown);
    return () => window.removeEventListener('mousedown', onDown);
  }, [viewOpen]);

  const currentMeta = VIEW_OPTIONS.find((v) => v.key === selectedView);
  const CurrentIcon = currentMeta?.Icon || Eye;

  const pickView = useCallback((mode) => {
    // Toggle si on reclique la vue déjà sélectionnée → décoche.
    const next = mode === selectedView ? '' : mode;
    setStoredViewMode(next || null);
    setSelectedView(next);
    setViewOpen(false);
  }, [selectedView]);

  const visitAccount = useCallback(() => {
    // Utilise la vue sélectionnée, sinon 'user' par défaut.
    const chosen = selectedView || 'user';
    setStoredViewMode(chosen);
    setSelectedView(chosen);
    // Marque comme simulation-unauth : si l'utilisateur décoche la vue
    // depuis le dashboard, il sera renvoyé sur /login (spec F iter150).
    setSimulationUnauth(true);
    navigate('/dashboard');
  }, [selectedView, navigate]);

  return (
    <div
      className="flex gap-1 p-1 bg-white/[0.02] border border-white/10 rounded-sm"
      data-testid="login-aux-row"
    >
      {/* GAUCHE — Visite du compte (mêmes largeur que « Connexion » tab) */}
      <button
        type="button"
        onClick={visitAccount}
        data-testid="login-visit-account-btn"
        title="Prévisualiser le site avec la vue actuelle (par défaut : Utilisateur inscrit)"
        className="flex-1 inline-flex items-center justify-center gap-1.5 py-2 text-xs sm:text-sm font-['Chivo'] font-bold rounded-sm border border-[#E4FF00]/40 text-[#E4FF00] hover:bg-[#E4FF00]/10 hover:border-[#E4FF00] transition-all min-w-0"
      >
        <Eye className="w-3.5 h-3.5 flex-shrink-0" />
        <span className="truncate">Visite du compte</span>
      </button>

      {/* DROITE — Choix de vue (mêmes largeur que « Inscription » tab) */}
      <div ref={wrapRef} className="flex-1 relative min-w-0">
        <button
          type="button"
          onClick={() => setViewOpen((v) => !v)}
          data-testid="login-view-picker-btn"
          aria-expanded={viewOpen}
          title={currentMeta ? `Vue actuelle : ${currentMeta.label}` : 'Choisir un type de vue à prévisualiser'}
          className={`w-full inline-flex items-center justify-center gap-1.5 py-2 text-xs sm:text-sm font-['Chivo'] font-bold rounded-sm border transition-all min-w-0 ${
            currentMeta
              ? 'border-[#E4FF00] bg-[#E4FF00]/10 text-[#E4FF00]'
              : viewOpen
              ? 'border-[#E4FF00] bg-[#E4FF00]/10 text-[#E4FF00]'
              : 'border-white/20 text-[#A1A1AA] hover:border-white/40 hover:text-white'
          }`}
        >
          <CurrentIcon className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="truncate" data-testid="login-view-picker-label">
            {currentMeta ? `Vue : ${currentMeta.short}` : 'Choix de vue'}
          </span>
          <ChevronDown className={`w-3.5 h-3.5 transition-transform flex-shrink-0 ${viewOpen ? 'rotate-180' : ''}`} />
        </button>
        {viewOpen && (
          <div
            data-testid="login-view-picker-dropdown"
            className="absolute right-0 top-full mt-2 w-72 max-w-[calc(100vw-2rem)] bg-[#0A0A0A] border border-white/15 rounded-sm shadow-2xl z-50"
          >
            <div className="px-3 py-1.5 text-[10px] uppercase tracking-widest text-[#71717A] border-b border-white/10">
              Choisir la vue à prévisualiser
            </div>
            {VIEW_OPTIONS.map(({ key, label, Icon, color, desc }) => {
              const active = key === selectedView;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => pickView(key)}
                  data-testid={`login-view-opt-${key}`}
                  className={`w-full text-left flex items-start gap-3 p-2.5 hover:bg-white/[0.05] transition-colors border-b border-white/5 last:border-b-0 ${
                    active ? 'bg-[#E4FF00]/5' : ''
                  }`}
                >
                  <span className={`w-4 h-4 mt-0.5 flex-shrink-0 border rounded-sm flex items-center justify-center ${
                    active ? 'border-[#E4FF00] bg-[#E4FF00]/20' : 'border-white/30'
                  }`}>
                    {active && <Check className="w-3 h-3 text-[#E4FF00]" />}
                  </span>
                  <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${color}`} />
                  <div className="min-w-0 flex-1">
                    <div className={`text-xs font-bold ${active ? 'text-[#E4FF00]' : 'text-white'}`}>
                      {label}
                    </div>
                    <div className="text-[10px] text-[#A1A1AA] mt-0.5">{desc}</div>
                  </div>
                </button>
              );
            })}
            <div className="px-3 py-2 text-[10px] text-[#71717A] border-t border-white/5 inline-flex items-center gap-1">
              <Lock className="w-3 h-3" />
              Aucune donnée personnelle requise
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
