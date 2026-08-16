/**
 * iter158.10 — P0.3 : Transfer Ownership UI (formulaire propriétaire).
 *
 * Expose le mécanisme backend existant :
 *   1. POST /ownership/challenge {action:'transfer_ownership', target_key_id}
 *      → renvoie {challenge_id, challenge_nonce, needs_double_signature:true}
 *   2. Sur l'appareil courant : signer le challenge_nonce → proof #1.
 *   3. L'utilisateur récupère une 2e signature sur son 2e appareil propriétaire
 *      (copier-coller de la signature base64url).
 *   4. POST /ownership/transfer {challenge_id, proofs:[2 sigs], new_owner_key_id}.
 *
 * SÉCURITÉ (spec P0.3 stricte) :
 *   - Backend reste l'autorité finale (double signature ECDSA vérifiée serveur).
 *   - Le frontend ne prétend PAS avoir un « mot de passe » — le mécanisme
 *     réel est cryptographique (2 signatures ECDSA de 2 appareils
 *     propriétaires distincts).
 *   - Aucun état frontend ne peut transférer la propriété sans les 2 preuves.
 *   - Composant visible UNIQUEMENT si is_owner=true (auto-gaté).
 *   - Double confirmation UX : saisir explicitement « TRANSFERT » +
 *     confirmation finale par bouton distinct.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import {
  Crown, X, AlertTriangle, ShieldCheck, Copy, ArrowRight, KeyRound, Loader2,
} from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof, signNonce } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STEPS = { INTRO: 0, CONFIRM: 1, CHALLENGE: 2, SIG2: 3, DONE: 4 };

export default function TransferOwnershipPanel({ open, onClose }) {
  const [isOwner, setIsOwner] = useState(false);
  const [selfKeyId, setSelfKeyId] = useState('');
  const [step, setStep] = useState(STEPS.INTRO);
  const [newOwnerKeyId, setNewOwnerKeyId] = useState('');
  const [confirmToken, setConfirmToken] = useState('');
  const [challenge, setChallenge] = useState(null); // {challenge_id, challenge_nonce, needs_double_signature}
  const [proof1, setProof1] = useState(null); // {key_id, signature}
  const [secondKeyId, setSecondKeyId] = useState('');
  const [secondSig, setSecondSig] = useState('');
  const [busy, setBusy] = useState(false);
  const [resultInfo, setResultInfo] = useState(null);

  // Vérifie is_owner + récupère le key_id courant.
  useEffect(() => {
    let cancelled = false;
    if (!open) return;
    (async () => {
      try {
        const body = await withCreatorProof(API, axios, {});
        const r = await axios.post(`${API}/ownership/status`, body);
        if (cancelled) return;
        setIsOwner(!!r.data?.is_owner);
        setSelfKeyId(body.key_id || '');
      } catch (_) {
        if (!cancelled) setIsOwner(false);
      }
    })();
    return () => { cancelled = true; };
  }, [open]);

  const reset = useCallback(() => {
    setStep(STEPS.INTRO);
    setNewOwnerKeyId('');
    setConfirmToken('');
    setChallenge(null);
    setProof1(null);
    setSecondKeyId('');
    setSecondSig('');
    setResultInfo(null);
  }, []);

  const close = () => { reset(); onClose && onClose(); };

  // Étape 1 → 2 : validation formulaire.
  const goConfirm = () => {
    if (!newOwnerKeyId.trim()) {
      toast.error('Identifiant du destinataire requis.');
      return;
    }
    if (newOwnerKeyId.trim() === selfKeyId) {
      toast.error('Le destinataire ne peut pas être ton propre appareil.');
      return;
    }
    setStep(STEPS.CONFIRM);
  };

  // Étape 2 → 3 : demander un challenge signé (proof #1 automatique).
  const requestChallenge = async () => {
    if (confirmToken !== 'TRANSFERT') {
      toast.error('Tape « TRANSFERT » exactement pour confirmer.');
      return;
    }
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, {
        action: 'transfer_ownership',
        target_key_id: newOwnerKeyId.trim(),
      });
      const r = await axios.post(`${API}/ownership/challenge`, body);
      const ch = r.data;
      if (!ch?.challenge_id) throw new Error('Challenge non émis');
      setChallenge(ch);
      // Signature immédiate de proof #1 par l'appareil courant.
      const sig = await signNonce(ch.challenge_nonce);
      setProof1({ key_id: selfKeyId, signature: sig });
      setStep(STEPS.SIG2);
      toast.success('Signature #1 générée sur cet appareil.');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Échec émission du challenge');
    } finally { setBusy(false); }
  };

  // Étape 3 → 4 : soumettre les 2 preuves.
  const submitTransfer = async () => {
    if (!secondKeyId.trim() || !secondSig.trim()) {
      toast.error('key_id + signature du 2e appareil propriétaire requis.');
      return;
    }
    if (secondKeyId.trim() === selfKeyId) {
      toast.error('Les 2 signatures doivent provenir d\'appareils DISTINCTS.');
      return;
    }
    setBusy(true);
    try {
      const proofs = [proof1, { key_id: secondKeyId.trim(), signature: secondSig.trim() }];
      const r = await axios.post(`${API}/ownership/transfer`, {
        challenge_id: challenge.challenge_id,
        proofs,
        new_owner_key_id: newOwnerKeyId.trim(),
      });
      setResultInfo(r.data);
      setStep(STEPS.DONE);
      toast.success('Transfert propriétaire réussi.');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Transfert refusé par le serveur');
    } finally { setBusy(false); }
  };

  const copyNonce = () => {
    if (challenge?.challenge_nonce) {
      navigator.clipboard.writeText(challenge.challenge_nonce);
      toast.success('challenge_nonce copié — colle-le dans le 2e appareil.');
    }
  };

  if (!open) return null;
  // Défense en profondeur : non-owner ne verra rien même si le composant est monté.
  if (!isOwner) {
    return (
      <div className="fixed inset-0 z-[87] bg-black/80 flex items-center justify-center p-3" onClick={close} data-testid="transfer-ownership-panel">
        <div onClick={(e) => e.stopPropagation()} className="w-full max-w-md bg-[#0A0A0A] border border-red-400/40 rounded-sm p-4 space-y-2">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <h3 className="text-sm font-bold uppercase tracking-widest text-red-300" data-testid="transfer-ownership-denied">
              Accès refusé
            </h3>
          </div>
          <p className="text-xs text-[#A1A1AA]">Cette fonction est réservée aux appareils propriétaires réels.</p>
          <button onClick={close} className="text-xs px-3 py-1.5 border border-white/15 text-white/80 rounded-sm">Fermer</button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[87] bg-black/85 flex items-start justify-center p-3 overflow-y-auto" onClick={close} data-testid="transfer-ownership-panel">
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-2xl bg-[#0A0A0A] border border-red-400/50 rounded-sm p-4 space-y-3 mt-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Crown className="w-4 h-4 text-red-400" />
            <h3 className="text-sm font-['Chivo'] font-bold uppercase tracking-widest text-white">
              Transfert de propriété
            </h3>
          </div>
          <button onClick={close} data-testid="transfer-ownership-close" className="text-[#A1A1AA] hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Avertissement CDC — toujours visible */}
        <div className="border border-red-400/50 bg-red-400/5 rounded-sm p-3 space-y-1">
          <div className="flex items-center gap-2 text-red-300 text-xs font-bold uppercase tracking-widest">
            <AlertTriangle className="w-3.5 h-3.5" />
            Action définitive
          </div>
          <p className="text-[11px] text-white/80 leading-relaxed">
            Ce transfert ajoute un nouvel appareil propriétaire à la propriété du site
            (spec CDC : « transmission définitive, notamment testament »). L'opération est
            journalisée et exige <strong>2 signatures ECDSA</strong> de 2 appareils propriétaires
            distincts. Aucun état frontend ne peut la déclencher seul.
          </p>
        </div>

        {/* Étape INTRO */}
        {step === STEPS.INTRO && (
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-widest text-[#71717A]">
              Identifiant du destinataire (`key_id` du nouvel appareil propriétaire)
            </label>
            <input
              value={newOwnerKeyId}
              onChange={(e) => setNewOwnerKeyId(e.target.value)}
              data-testid="transfer-ownership-new-key"
              placeholder="Ex: eyJrdHkiOiJFQyI..."
              className="w-full bg-black/40 border border-white/10 rounded-sm px-2 py-2 text-xs text-white font-['IBM_Plex_Mono'] focus:outline-none focus:border-red-400"
            />
            <p className="text-[10px] text-[#71717A]">
              Cet appareil doit déjà exister dans <code>device_keys</code> (l'utilisateur
              doit s'être connecté au moins une fois).
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={close} data-testid="transfer-ownership-cancel-intro" className="text-xs px-3 py-1.5 border border-white/15 text-white/80 rounded-sm">Annuler</button>
              <button
                onClick={goConfirm}
                disabled={!newOwnerKeyId.trim()}
                data-testid="transfer-ownership-continue-intro"
                className="text-xs px-3 py-1.5 border border-red-400/60 text-red-300 hover:bg-red-400/10 rounded-sm disabled:opacity-40 inline-flex items-center gap-1"
              >
                Continuer <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        )}

        {/* Étape CONFIRM */}
        {step === STEPS.CONFIRM && (
          <div className="space-y-2">
            <div className="text-xs text-white/80">
              Destinataire : <span className="font-['IBM_Plex_Mono'] text-red-300 break-all">{newOwnerKeyId}</span>
            </div>
            <label className="text-xs uppercase tracking-widest text-[#71717A]">
              Confirme en tapant : <span className="text-red-300 font-bold">TRANSFERT</span>
            </label>
            <input
              value={confirmToken}
              onChange={(e) => setConfirmToken(e.target.value)}
              data-testid="transfer-ownership-confirm-token"
              placeholder="TRANSFERT"
              className="w-full bg-black/40 border border-white/10 rounded-sm px-2 py-2 text-xs text-white font-['IBM_Plex_Mono'] focus:outline-none focus:border-red-400"
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setStep(STEPS.INTRO)} className="text-xs px-3 py-1.5 border border-white/15 text-white/80 rounded-sm">Retour</button>
              <button
                onClick={requestChallenge}
                disabled={busy || confirmToken !== 'TRANSFERT'}
                data-testid="transfer-ownership-request-challenge"
                className="text-xs px-3 py-1.5 border border-red-400/60 text-red-300 hover:bg-red-400/10 rounded-sm disabled:opacity-40 inline-flex items-center gap-1"
              >
                {busy && <Loader2 className="w-3 h-3 animate-spin" />}
                Émettre le challenge & signer <KeyRound className="w-3 h-3" />
              </button>
            </div>
          </div>
        )}

        {/* Étape SIG2 (challenge émis, proof1 signé, en attente de sig2) */}
        {step === STEPS.SIG2 && challenge && (
          <div className="space-y-3">
            <div className="border border-emerald-400/40 bg-emerald-400/5 rounded-sm p-2 text-[11px] text-emerald-200">
              <ShieldCheck className="inline w-3 h-3 mr-1" />
              Signature #1 générée par cet appareil (<code>{selfKeyId.slice(0, 20)}…</code>).
            </div>
            <div className="space-y-1">
              <label className="text-xs uppercase tracking-widest text-[#71717A]">
                Défi à signer sur le 2e appareil propriétaire
              </label>
              <div className="flex gap-2 items-center">
                <code className="flex-1 bg-black/40 border border-white/10 rounded-sm px-2 py-2 text-[10px] text-white font-['IBM_Plex_Mono'] break-all" data-testid="transfer-ownership-nonce">
                  {challenge.challenge_nonce}
                </code>
                <button onClick={copyNonce} data-testid="transfer-ownership-copy-nonce" className="p-2 border border-white/15 text-[#A1A1AA] hover:text-white rounded-sm" title="Copier">
                  <Copy className="w-3 h-3" />
                </button>
              </div>
              <p className="text-[10px] text-[#71717A]">
                Sur le 2e appareil propriétaire, connecte-toi et signe ce nonce
                (fonction dev : <code>signNonce(nonce)</code> exposée en console). Colle ci-dessous.
              </p>
            </div>
            <div className="space-y-1">
              <label className="text-xs uppercase tracking-widest text-[#71717A]">
                key_id du 2e appareil propriétaire
              </label>
              <input
                value={secondKeyId}
                onChange={(e) => setSecondKeyId(e.target.value)}
                data-testid="transfer-ownership-sig2-keyid"
                placeholder="key_id du 2e appareil"
                className="w-full bg-black/40 border border-white/10 rounded-sm px-2 py-2 text-xs text-white font-['IBM_Plex_Mono'] focus:outline-none focus:border-red-400"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs uppercase tracking-widest text-[#71717A]">
                Signature (base64url)
              </label>
              <textarea
                value={secondSig}
                onChange={(e) => setSecondSig(e.target.value)}
                data-testid="transfer-ownership-sig2-value"
                placeholder="Colle la signature du 2e appareil"
                rows={2}
                className="w-full bg-black/40 border border-white/10 rounded-sm px-2 py-2 text-xs text-white font-['IBM_Plex_Mono'] focus:outline-none focus:border-red-400"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={close} data-testid="transfer-ownership-cancel-sig2" className="text-xs px-3 py-1.5 border border-white/15 text-white/80 rounded-sm">Annuler</button>
              <button
                onClick={submitTransfer}
                disabled={busy || !secondKeyId.trim() || !secondSig.trim()}
                data-testid="transfer-ownership-submit"
                className="text-xs px-3 py-1.5 border border-red-500/70 text-red-200 bg-red-500/10 hover:bg-red-500/20 rounded-sm disabled:opacity-40 inline-flex items-center gap-1"
              >
                {busy && <Loader2 className="w-3 h-3 animate-spin" />}
                Confirmer le transfert (double signature)
              </button>
            </div>
          </div>
        )}

        {/* Étape DONE */}
        {step === STEPS.DONE && resultInfo && (
          <div className="space-y-2">
            <div className="border border-emerald-400/50 bg-emerald-400/5 rounded-sm p-3 text-[11px] text-emerald-200 space-y-1" data-testid="transfer-ownership-success">
              <div className="flex items-center gap-2 font-bold uppercase tracking-widest">
                <ShieldCheck className="w-4 h-4" /> Transfert réussi
              </div>
              <div>Nouvel appareil propriétaire : <code className="break-all">{resultInfo.new_owner}</code></div>
              {resultInfo.owner_user_id && (
                <div>owner_user_id : <code className="break-all">{resultInfo.owner_user_id}</code></div>
              )}
            </div>
            <div className="flex justify-end">
              <button onClick={close} className="text-xs px-3 py-1.5 border border-white/15 text-white/80 rounded-sm">Fermer</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
