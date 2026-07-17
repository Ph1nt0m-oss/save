/**
 * iter134/136/137 — WhoCanVisitBadge (créa-only)
 *
 * Onglet "Mode de choix de vue" : Libre / Vue forcée par la créa.
 *
 * • Libre choix  : l'utilisateur choisit librement parmi toutes les vues
 *                  (créa, user, modo, admin, guest) — message explicatif.
 * • Vue forcée   : la créa coche les vues autorisées ; l'utilisateur ne
 *                  peut sélectionner QUE parmi celles-là (min 1 requise).
 *
 * Écrit sur PUT /api/system/who-can-visit — envoie `view_forcing` et
 * `forced_views` (les 2 champs sont optionnels côté backend).
 */
import React, { useState } from 'react';
import axios from 'axios';
import { ChevronDown, UserCog, Radio, Check, ShieldQuestion } from 'lucide-react';
import { SITE_MODE_KEYS } from '../lib/siteModeKeys';
import { withCreatorProof } from '../lib/deviceIdentity';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// iter138 — Même liste partagée que les 3 autres onglets (privé, public,
// invité, utilisateurs, modo, admin, créa). La sémantique en mode 'Vue
// forcée' : la créa coche les vues autorisées pour le visiteur.
const VIEW_KEYS = SITE_MODE_KEYS;

export default function WhoCanVisitBadge({
  role, viewForcing = 'free', visitModes = [], forcedViews = [],
  onChange, className = '',
  controlledOpen, onOpenChange,
} = {}) {
  const [internalOpen, setInternalOpen] = useState(false);
  const open = controlledOpen !== undefined ? controlledOpen : internalOpen;
  const setOpen = (v) => {
    const next = typeof v === 'function' ? v(open) : v;
    if (onOpenChange) onOpenChange(next);
    else setInternalOpen(next);
  };
  const [saving, setSaving] = useState(false);

  const isCreator = role === 'creator';
  const forcing = viewForcing === 'forced' ? 'forced' : 'free';
  const activeForced = Array.isArray(forcedViews) ? forcedViews : [];

  const savePayload = async (payload, successMsg) => {
    if (!isCreator || saving) return;
    setSaving(true);
    try {
      const body = await withCreatorProof(API, axios, payload);
      await axios.put(`${API}/system/who-can-visit`, body);
      if (successMsg) toast.success(successMsg);
      onChange?.(payload);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec de la mise à jour.');
    } finally {
      setSaving(false);
    }
  };

  const setForcing = (mode) => {
    if (mode === forcing) return;
    // Passer en "forced" avec 0 vue → on préinitialise à 'user' pour éviter
    // un état bloquant (aucune vue sélectionnable côté utilisateur).
    if (mode === 'forced' && activeForced.length === 0) {
      savePayload(
        { view_forcing: 'forced', forced_views: ['user'] },
        'Vue forcée activée (Utilisateurs par défaut)',
      );
    } else {
      savePayload(
        { view_forcing: mode },
        mode === 'forced' ? 'Vue forcée activée' : 'Libre choix activé',
      );
    }
  };

  const toggleForcedView = (id) => {
    const isActive = activeForced.includes(id);
    if (isActive && activeForced.length === 1) {
      toast.error('En mode forcé, au moins une vue doit rester cochée.');
      return;
    }
    const next = isActive ? activeForced.filter((v) => v !== id) : [...activeForced, id];
    savePayload({ forced_views: next });
  };

  if (!isCreator) return null;

  const btnColor = forcing === 'forced'
    ? 'bg-[#E4FF00]/10 border-[#E4FF00]/40 text-[#E4FF00] hover:bg-[#E4FF00]/20'
    : 'bg-cyan-500/10 border-cyan-400/40 text-cyan-300 hover:bg-cyan-500/20';

  return (
    <div className={`relative inline-block ${className}`} data-testid="who-can-visit-creator">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={saving}
        data-testid="who-can-visit-toggle"
        title="Mode de choix de vue (Libre / Forcée)"
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-sm border transition-colors ${btnColor}`}
      >
        <UserCog className="w-3.5 h-3.5" />
        <span>{forcing === 'forced' ? 'Vue forcée' : 'Libre choix'}</span>
        {forcing === 'forced' && activeForced.length > 0 && (
          <span className="text-[9px] uppercase tracking-widest opacity-80">
            {activeForced.length === 1 ? activeForced[0] : `${activeForced.length}`}
          </span>
        )}
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          data-testid="who-can-visit-dropdown"
          className="absolute right-0 mt-1.5 w-80 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_10px_40px_rgba(0,0,0,0.6)] z-50 py-1 max-h-[560px] overflow-y-auto"
        >
          <div className="px-3 py-2 text-[10px] uppercase tracking-widest text-[#71717A] border-b border-white/10">
            Mode de choix de vue
          </div>

          {/* Les 2 radios */}
          <div className="p-2 space-y-1 border-b border-white/10">
            <button
              type="button"
              onClick={() => setForcing('free')}
              disabled={saving}
              data-testid="who-visit-forcing-free"
              className={`w-full text-left px-2 py-1.5 rounded-sm text-xs flex items-start gap-2 transition ${
                forcing === 'free' ? 'bg-cyan-500/15 text-cyan-300' : 'text-white hover:bg-white/[0.05]'
              }`}
            >
              <span className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 border rounded-full flex items-center justify-center ${
                forcing === 'free' ? 'border-cyan-300 bg-cyan-300/25' : 'border-white/30'
              }`}>
                {forcing === 'free' && <span className="w-1.5 h-1.5 rounded-full bg-cyan-300" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-['Chivo'] font-bold">Libre choix</div>
                <div className="text-[10px] text-[#A1A1AA]">L&apos;utilisateur décide de la vue qu&apos;il souhaite</div>
              </div>
            </button>
            <button
              type="button"
              onClick={() => setForcing('forced')}
              disabled={saving}
              data-testid="who-visit-forcing-forced"
              className={`w-full text-left px-2 py-1.5 rounded-sm text-xs flex items-start gap-2 transition ${
                forcing === 'forced' ? 'bg-[#E4FF00]/15 text-[#E4FF00]' : 'text-white hover:bg-white/[0.05]'
              }`}
            >
              <span className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 border rounded-full flex items-center justify-center ${
                forcing === 'forced' ? 'border-[#E4FF00] bg-[#E4FF00]/25' : 'border-white/30'
              }`}>
                {forcing === 'forced' && <span className="w-1.5 h-1.5 rounded-full bg-[#E4FF00]" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-['Chivo'] font-bold">Vue forcée par la créa</div>
                <div className="text-[10px] text-[#A1A1AA]">L&apos;utilisateur ne peut sélectionner qu&apos;une vue autorisée ci-dessous</div>
              </div>
            </button>
          </div>

          {/* Section conditionnelle : message en mode libre, sélecteur en mode forcé */}
          {forcing === 'free' ? (
            <div
              data-testid="mode-de-vue-free-message"
              className="px-3 py-3 text-[11px] text-cyan-200/90 flex items-start gap-1.5"
            >
              <Radio className="w-3 h-3 mt-0.5 flex-shrink-0 text-cyan-300" />
              <span>
                <strong className="text-cyan-300">Libre choix actif</strong> — l&apos;utilisateur choisit parmi les 5 vues : créatrice, utilisateur, modérateur, admin, invité. Pour restreindre son choix, active <em>Vue forcée</em>.
              </span>
            </div>
          ) : (
            <div>
              <div className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-widest text-[#71717A] flex items-center gap-1.5">
                <span>Vues autorisées en mode forcé</span>
                <span className="text-[9px] normal-case text-[#A1A1AA] tracking-normal">(minimum 1)</span>
              </div>
              {VIEW_KEYS.map((v) => {
                const Vi = v.icon;
                const isActive = activeForced.includes(v.id);
                const isLastActive = isActive && activeForced.length === 1;
                return (
                  <button
                    key={v.id}
                    type="button"
                    onClick={() => toggleForcedView(v.id)}
                    disabled={saving || isLastActive}
                    data-testid={`forced-view-option-${v.id}`}
                    title={isLastActive ? 'Au moins une vue doit rester cochée' : v.hint}
                    className={`w-full text-left px-3 py-2 text-xs hover:bg-white/[0.05] flex items-start gap-2 ${
                      isActive ? 'text-[#E4FF00] bg-[#E4FF00]/5' : 'text-white'
                    } ${isLastActive ? 'cursor-not-allowed' : ''}`}
                  >
                    <span className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 border rounded-sm flex items-center justify-center ${
                      isActive ? 'border-[#E4FF00] bg-[#E4FF00]/20' : 'border-white/30'
                    }`}>
                      {isActive && <Check className="w-2.5 h-2.5 text-[#E4FF00]" />}
                    </span>
                    <Vi className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="font-['Chivo'] font-bold inline-flex items-center gap-1">
                        {v.label}
                        {isLastActive && (
                          <span
                            data-testid={`forced-view-locked-${v.id}`}
                            title="Minimum une vue obligatoire en mode forcé"
                            className="inline-flex items-center gap-0.5 text-[8px] uppercase tracking-widest text-amber-300 border border-amber-400/40 bg-amber-400/10 rounded-sm px-1"
                          >
                            <ShieldQuestion className="w-2.5 h-2.5" /> verrouillé
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-[#A1A1AA]">{v.hint}</div>
                    </div>
                  </button>
                );
              })}
              <div className="px-3 py-2 border-t border-white/10 text-[10px] text-[#71717A] italic">
                Les utilisateurs verront uniquement les vues cochées ci-dessus dans leur sélecteur.
              </div>
            </div>
          )}

          {/* Rappel : où se configure "Qui peut voir" (audiences) */}
          <div className="px-3 py-2 border-t border-white/10 text-[10px] text-[#71717A] italic">
            Note : les <strong>audiences</strong> (privé, public, guest, modo, admin, créa) se configurent dans l&apos;onglet « Qui peut voir » (à gauche).
            {Array.isArray(visitModes) && visitModes.length > 0 && (
              <span className="ml-1 text-[#A1A1AA]">Actuelles : {visitModes.join(', ')}.</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
