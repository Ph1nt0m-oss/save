/**
 * iter142 — Bouton "Visite du menu" affiché AVANT les CTAs Connexion/
 * Inscription sur Landing + Login. Ouvre une petite feuille permettant de
 * choisir une vue (utilisateur / invité / privé) et de LANCER la
 * simulation du menu (dashboard) comme si on était connecté sous ce rôle.
 *
 * Contrairement à ViewModePicker (réservé à la Créa), ce composant est
 * disponible à TOUS les visiteurs. Il stocke temporairement la vue
 * choisie via `setStoredViewMode` puis navigue vers /dashboard.
 *
 * Design : bouton avec icône œil, ouvre un mini menu avec 3 options.
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, User, EyeOff, Lock, ChevronDown } from 'lucide-react';
import { setStoredViewMode } from '../hooks/useDeviceIdentity';

const OPTIONS = [
  { key: 'user',  label: 'Utilisateurs', Icon: User,   desc: 'Vue d\'un utilisateur inscrit' },
  { key: 'guest', label: 'Invité',       Icon: EyeOff, desc: 'Vue sans compte (lecture seule)' },
];

export default function PreviewMenuButton({ className = '' }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const preview = (mode) => {
    setStoredViewMode(mode);
    setOpen(false);
    navigate('/dashboard');
  };

  return (
    <div className={`relative inline-block ${className}`} data-testid="preview-menu-wrap">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        data-testid="preview-menu-btn"
        title="Visiter le menu sans compte"
        aria-expanded={open}
        className="inline-flex items-center gap-2 px-6 sm:px-8 py-3 sm:py-4 border border-[#E4FF00]/40 text-[#E4FF00] text-base sm:text-lg font-['Chivo'] font-bold rounded-sm hover:bg-[#E4FF00]/10 hover:border-[#E4FF00] transition-all duration-200"
      >
        <Eye className="w-4 h-4" />
        Visite du menu
        <ChevronDown className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div
          className="absolute left-1/2 -translate-x-1/2 top-full mt-2 w-64 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-2xl z-50"
          data-testid="preview-menu-dropdown"
        >
          {OPTIONS.map(({ key, label, Icon, desc }) => (
            <button
              key={key}
              type="button"
              onClick={() => preview(key)}
              data-testid={`preview-opt-${key}`}
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
  );
}
