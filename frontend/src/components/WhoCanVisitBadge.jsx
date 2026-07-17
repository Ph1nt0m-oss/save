/**
 * iter134 — Composant WhoCanVisitBadge (créa-only).
 *
 * Onglet demandé par l'utilisateur : "Qui peut visiter ?" — configure les
 * vues autorisées pour les visiteurs (multi-sélection des 6 clés) et si
 * l'utilisateur a le libre choix ou si la créa lui force une vue.
 *
 * Placement : dans le header, entre SiteModeBadge et ViewModePicker.
 *
 * Contrat data-testid :
 *   who-can-visit-toggle              → bouton principal
 *   who-can-visit-dropdown            → dropdown ouvert
 *   who-visit-forcing-free            → radio "Libre choix"
 *   who-visit-forcing-forced          → radio "Vue forcée par la créa"
 *   who-visit-option-<id>             → checkbox par clé (private/public/guest/modo/admin/creator)
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Eye, Check, ChevronDown, Lock, Globe, EyeOff, ShieldAlert, ShieldCheck, Crown, UserCog, Info } from 'lucide-react';
import { withCreatorProof } from '../lib/deviceIdentity';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const VISIT_MODES = [
  { id: 'private', icon: Lock,        label: 'Privé',    hint: 'Clés validées uniquement' },
  { id: 'public',  icon: Globe,       label: 'Public',   hint: 'Ouvert à tous' },
  { id: 'guest',   icon: EyeOff,      label: 'Guest',    hint: 'Lecture seule (non approuvés)' },
  { id: 'modo',    icon: ShieldAlert, label: 'Modo',     hint: 'Modérateurs uniquement' },
  { id: 'admin',   icon: ShieldCheck, label: 'Admin',    hint: 'Administrateurs uniquement' },
  { id: 'creator', icon: Crown,       label: 'Créa',     hint: 'Créatrice uniquement' },
];

export default function WhoCanVisitBadge({
  role, visitModes = ['public'], viewForcing = 'free',
  siteModes = [],
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
  const active = Array.isArray(visitModes) && visitModes.length ? visitModes : ['public'];
  // iter135 — Si "Invité" (guest) est coché dans le TYPE DE SITE (siteModes),
  // le mode "Vue forcée par la créa" est INTERDIT (règle métier utilisateur).
  // Note : ce blocage ne concerne PAS le fait de cocher 'guest' dans les
  // vues autorisées (mode de choix de vue) — uniquement le siteModes.
  const guestInSiteMode = Array.isArray(siteModes) && siteModes.includes('guest');
  const forcing = guestInSiteMode ? 'free' : (viewForcing === 'forced' ? 'forced' : 'free');

  // iter135 — Auto-correction : si le backend a 'forced' mais que 'guest'
  // vient d'être coché en site type, on repasse à 'free' silencieusement.
  useEffect(() => {
    if (guestInSiteMode && viewForcing === 'forced' && isCreator) {
      (async () => {
        try {
          const body = await withCreatorProof(API, axios, {
            visit_modes: active, view_forcing: 'free',
          });
          await axios.put(`${API}/system/who-can-visit`, body);
          onChange?.(active, 'free');
        } catch (_e) { /* silent */ }
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guestInSiteMode]);

  const save = async (nextModes, nextForcing) => {
    if (!isCreator || saving) return;
    // Au moins 1 mode requis
    let finalModes = nextModes.filter((m) => VISIT_MODES.some((v) => v.id === m));
    if (finalModes.length === 0) finalModes = ['public'];
    setSaving(true);
    try {
      const body = await withCreatorProof(API, axios, {
        visit_modes: finalModes,
        view_forcing: nextForcing,
      });
      await axios.put(`${API}/system/who-can-visit`, body);
      toast.success(`Qui peut visiter : ${finalModes.join(', ')} (${nextForcing === 'forced' ? 'forcé' : 'libre'})`);
      onChange?.(finalModes, nextForcing);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec de la mise à jour.');
    } finally {
      setSaving(false);
    }
  };

  const toggleMode = (id) => {
    let next = active.filter((m) => m !== id);
    if (!active.includes(id)) next = [...active, id];
    save(next, forcing);
  };

  const setForcing = (mode) => {
    if (mode === forcing) return;
    if (mode === 'forced' && guestInSiteMode) {
      toast.warning('Décoche d\'abord "Invité" dans le type de site pour activer la vue forcée.');
      return;
    }
    save(active, mode);
  };

  if (!isCreator) return null;

  const displayLabel = active.length === 1 ? (VISIT_MODES.find((m) => m.id === active[0])?.label || active[0])
    : active.length <= 2 ? active.map((a) => VISIT_MODES.find((m) => m.id === a)?.label || a).join(' · ')
    : `${active.length} vues`;

  return (
    <div className={`relative inline-block ${className}`} data-testid="who-can-visit-creator">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={saving}
        data-testid="who-can-visit-toggle"
        title="Qui peut visiter le site & mode de choix de vue"
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-sm border transition-colors ${
          forcing === 'forced'
            ? 'bg-[#E4FF00]/10 border-[#E4FF00]/40 text-[#E4FF00] hover:bg-[#E4FF00]/20'
            : 'bg-cyan-500/10 border-cyan-400/40 text-cyan-300 hover:bg-cyan-500/20'
        }`}
      >
        <UserCog className="w-3.5 h-3.5" />
        <Eye className="w-3.5 h-3.5" />
        <span>{displayLabel}</span>
        {forcing === 'forced' && <span className="text-[9px] uppercase tracking-widest">forcé</span>}
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          data-testid="who-can-visit-dropdown"
          className="absolute right-0 mt-1.5 w-80 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_10px_40px_rgba(0,0,0,0.6)] z-50 py-1 max-h-[520px] overflow-y-auto"
        >
          {/* Radios en haut : Libre choix / Vue forcée */}
          <div className="px-3 py-2 border-b border-white/10">
            <div className="text-[10px] uppercase tracking-widest text-[#71717A] mb-2">Mode de choix de vue</div>
            {guestInSiteMode && (
              <div
                data-testid="who-visit-guest-blocks-forced"
                className="mb-2 flex items-start gap-1.5 text-[10px] text-amber-200/90 border border-amber-400/30 bg-amber-400/10 rounded-sm px-2 py-1.5"
              >
                <Info className="w-3 h-3 mt-0.5 flex-shrink-0" />
                <span>Mode "Vue forcée" indisponible : "Invité" est coché dans le type de site. Décoche-le d'abord pour l'activer.</span>
              </div>
            )}
            <div className="space-y-1">
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
                disabled={saving || guestInSiteMode}
                data-testid="who-visit-forcing-forced"
                title={guestInSiteMode ? 'Décoche "Invité" dans le type de site pour activer la vue forcée' : undefined}
                className={`w-full text-left px-2 py-1.5 rounded-sm text-xs flex items-start gap-2 transition ${
                  guestInSiteMode
                    ? 'text-white/40 cursor-not-allowed'
                    : (forcing === 'forced' ? 'bg-[#E4FF00]/15 text-[#E4FF00]' : 'text-white hover:bg-white/[0.05]')
                }`}
              >
                <span className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 border rounded-full flex items-center justify-center ${
                  forcing === 'forced' && !guestInSiteMode
                    ? 'border-[#E4FF00] bg-[#E4FF00]/25'
                    : 'border-white/30'
                }`}>
                  {forcing === 'forced' && !guestInSiteMode && <span className="w-1.5 h-1.5 rounded-full bg-[#E4FF00]" />}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-['Chivo'] font-bold">Vue forcée par la créa</div>
                  <div className="text-[10px] text-[#A1A1AA]">L&apos;utilisateur ne peut sélectionner qu&apos;une vue autorisée</div>
                </div>
              </button>
            </div>
          </div>

          {/* Multi-select des 6 clés (au moins 1 requise) */}
          <div className="px-3 py-2 text-[10px] uppercase tracking-widest text-[#71717A] border-b border-white/10">
            Vues autorisées (multi-sélection, minimum 1)
          </div>
          {VISIT_MODES.map((m) => {
            const Mi = m.icon;
            const isActive = active.includes(m.id);
            const isLastActive = isActive && active.length === 1;
            // iter135 — Coloration jaune #E4FF00 quand "Vue forcée" est active,
            // sinon cyan par défaut. Les cases actives suivent le mode courant.
            const isForced = forcing === 'forced';
            const activeText = isForced ? 'text-[#E4FF00]' : 'text-cyan-300';
            const activeBg = isForced ? 'bg-[#E4FF00]/5' : 'bg-cyan-500/5';
            const activeBorder = isForced ? 'border-[#E4FF00] bg-[#E4FF00]/20' : 'border-cyan-300 bg-cyan-300/20';
            const activeCheck = isForced ? 'text-[#E4FF00]' : 'text-cyan-300';
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => toggleMode(m.id)}
                disabled={saving || isLastActive}
                data-testid={`who-visit-option-${m.id}`}
                title={isLastActive ? 'Au moins une vue doit rester cochée' : m.hint}
                className={`w-full text-left px-3 py-2 text-xs hover:bg-white/[0.05] flex items-start gap-2 ${
                  isActive ? `${activeText} ${activeBg}` : 'text-white'
                } ${isLastActive ? 'opacity-70 cursor-not-allowed' : ''}`}
              >
                <span className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 border rounded-sm flex items-center justify-center ${
                  isActive ? activeBorder : 'border-white/30'
                }`}>
                  {isActive && <Check className={`w-2.5 h-2.5 ${activeCheck}`} />}
                </span>
                <Mi className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="font-['Chivo'] font-bold">{m.label}</div>
                  <div className="text-[10px] text-[#A1A1AA]">{m.hint}</div>
                </div>
              </button>
            );
          })}

          <div className="px-3 py-2 border-t border-white/10 text-[10px] text-[#71717A] italic">
            {forcing === 'forced'
              ? '⚠ En mode forcé, les utilisateurs ne pourront pas basculer vers une vue non cochée.'
              : 'Les utilisateurs pourront choisir librement parmi les vues autorisées.'}
          </div>
        </div>
      )}
    </div>
  );
}
