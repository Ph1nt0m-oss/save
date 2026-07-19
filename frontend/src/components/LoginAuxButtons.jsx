/**
 * iter149 — LoginAuxButtons : "Visite du compte" + "Choix de vue".
 *
 * Remplace le PreviewMenuButton (image 3) qui affichait Utilisateurs +
 * Invité dans un unique dropdown. Selon la spec A/B :
 *
 *   [ Visite du compte ]  [ Choix de vue ▾ ]
 *   ← même largeur que        ← même largeur
 *      Connexion tab             que Inscription tab
 *
 * - « Visite du compte » (gauche) : bouton simple → lance la simulation
 *   d'un compte inscrit (mode 'user' par défaut). Correspond à la
 *   volonté « visiter » l'app sans passer par la connexion.
 * - « Choix de vue » (droite)     : dropdown listant les types de vue
 *   disponibles (Utilisateur inscrit / Invité). Le clic sur une option
 *   ouvre la simulation.
 *
 * Alignement responsive : les deux boutons partagent la même hauteur
 * (py-2, comme les tabs Connexion/Inscription) et se plient en flex-1
 * pour occuper 50 % chacun de la largeur du conteneur.
 */
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, User, EyeOff, Lock, ChevronDown } from 'lucide-react';
import { setStoredViewMode } from '../hooks/useDeviceIdentity';

const VIEW_OPTIONS = [
  { key: 'user',  label: 'Utilisateur inscrit', Icon: User,   desc: 'Vue d\'un utilisateur connecté' },
  { key: 'guest', label: 'Invité (lecture seule)', Icon: EyeOff, desc: 'Vue sans compte, aucune donnée écrite' },
];

export default function LoginAuxButtons() {
  const navigate = useNavigate();
  const [viewOpen, setViewOpen] = useState(false);
  const wrapRef = useRef(null);

  // Ferme le dropdown au clic extérieur.
  useEffect(() => {
    if (!viewOpen) return undefined;
    const onDown = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setViewOpen(false);
    };
    window.addEventListener('mousedown', onDown);
    return () => window.removeEventListener('mousedown', onDown);
  }, [viewOpen]);

  const launchView = (mode) => {
    setStoredViewMode(mode);
    setViewOpen(false);
    navigate('/dashboard');
  };

  return (
    <div className="flex gap-1 p-1 bg-white/[0.02] border border-white/10 rounded-sm" data-testid="login-aux-row">
      {/* GAUCHE — Visite du compte (même largeur que "Connexion" tab) */}
      <button
        type="button"
        onClick={() => launchView('user')}
        data-testid="login-visit-account-btn"
        title="Visiter l'app comme un utilisateur inscrit"
        className="flex-1 inline-flex items-center justify-center gap-1.5 py-2 text-xs sm:text-sm font-['Chivo'] font-bold rounded-sm border border-[#E4FF00]/40 text-[#E4FF00] hover:bg-[#E4FF00]/10 hover:border-[#E4FF00] transition-all"
      >
        <Eye className="w-3.5 h-3.5" />
        <span className="truncate">Visite du compte</span>
      </button>

      {/* DROITE — Choix de vue (même largeur que "Inscription" tab) */}
      <div ref={wrapRef} className="flex-1 relative">
        <button
          type="button"
          onClick={() => setViewOpen((v) => !v)}
          data-testid="login-view-picker-btn"
          aria-expanded={viewOpen}
          title="Choisir un type de vue à prévisualiser"
          className={`w-full inline-flex items-center justify-center gap-1.5 py-2 text-xs sm:text-sm font-['Chivo'] font-bold rounded-sm border transition-all ${
            viewOpen
              ? 'border-[#E4FF00] bg-[#E4FF00]/10 text-[#E4FF00]'
              : 'border-white/20 text-[#A1A1AA] hover:border-white/40 hover:text-white'
          }`}
        >
          <span className="truncate">Choix de vue</span>
          <ChevronDown className={`w-3.5 h-3.5 transition-transform ${viewOpen ? 'rotate-180' : ''}`} />
        </button>
        {viewOpen && (
          <div
            data-testid="login-view-picker-dropdown"
            className="absolute right-0 top-full mt-2 w-64 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-2xl z-50"
          >
            {VIEW_OPTIONS.map(({ key, label, Icon, desc }) => (
              <button
                key={key}
                type="button"
                onClick={() => launchView(key)}
                data-testid={`login-view-opt-${key}`}
                className="w-full text-left flex items-start gap-3 p-3 hover:bg-white/[0.05] transition-colors border-b border-white/5 last:border-b-0"
              >
                <Icon className="w-4 h-4 text-[#E4FF00] mt-0.5 flex-shrink-0" />
                <div className="min-w-0">
                  <div className="text-sm text-white font-bold">{label}</div>
                  <div className="text-[11px] text-[#A1A1AA] mt-0.5">{desc}</div>
                </div>
              </button>
            ))}
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
