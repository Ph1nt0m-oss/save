import React, { useState } from 'react';
import axios from 'axios';
import { ShieldCheck, Loader2, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * iter125 — Requester-side popup that surfaces ONE of three states:
 *  - pending: friendly waiting message (no auto-close, no X).
 *  - approved: invites the user to click YES to download in chosen format.
 *  - rejected: explains the situation. Clicking YES sends the requester's
 *    device public key to the créa with the mention « Projet décliné »
 *    (re-uses the existing share-key flow used by the "Envoyer ma clé" button).
 *
 * No close icon — only the "Avez-vous bien lu… OUI" button hides the popup.
 *  - pending OUI  → no-op (visual ack).
 *  - rejected OUI → send key + toast + hide.
 *  - approved OUI → trigger download via the parent's `onApprovedDownload`
 *                   callback then hide.
 *
 * Backdrop is solid (z-125) but the rest of the page logic isn't blocked
 * (the parent decides whether to keep polling). The user keeps full access
 * to AccountsButton + Visite + language toggle — the only modal-blocked
 * surfaces are the Dashboard cards & sidebar buttons covered by the
 * `popup-blocker-overlay` rendered by Dashboard / Chat themselves.
 */
export default function ExportInReviewModal({
  open, status, kind, requestId, onApprovedDownload, onAcknowledge,
}) {
  const { t } = useLanguage();
  const [sendingKey, setSendingKey] = useState(false);
  const [downloading, setDownloading] = useState(false);

  if (!open) return null;

  const isApproved = status === 'approved';
  const isRejected = status === 'rejected';
  const isPending = !isApproved && !isRejected;

  const displayKind = (() => {
    if (!kind) return 'ZIP';
    const k = String(kind).toLowerCase();
    if (k.startsWith('zip')) return 'ZIP';
    if (k === 'apk') return 'APK';
    if (k === 'exe') return 'EXE';
    return k.toUpperCase();
  })();

  const sendKeyToCreator = async () => {
    setSendingKey(true);
    try {
      // iter125 — Reuse the existing "send key to creator" flow.
      // Mention "Projet décliné" + the rejected request_id for audit.
      const body = await withCreatorProof(API, axios, {
        send_to_admin: false,
        send_to_modo: false,
        reason: 'Projet décliné',
        request_id: requestId,
      });
      await axios.post(`${API}/devices/send-to-creator`, body);
      toast.success(t('exp_rejected_key_sent'));
    } catch (e) {
      // Best-effort; still close so the user isn't stuck.
      // eslint-disable-next-line no-console
      console.warn('send key to creator failed', e);
      toast.message(t('exp_rejected_key_sent'));
    } finally {
      setSendingKey(false);
      onAcknowledge?.();
    }
  };

  const handleOui = async () => {
    if (isPending) {
      // Visual ack only — keep the modal closed but polling continues
      // in the background.
      onAcknowledge?.();
      return;
    }
    if (isRejected) {
      await sendKeyToCreator();
      return;
    }
    if (isApproved) {
      setDownloading(true);
      try {
        await onApprovedDownload?.();
      } finally {
        setDownloading(false);
        onAcknowledge?.();
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-[125] flex items-center justify-center bg-black/92 backdrop-blur-md p-3 sm:p-6"
      data-testid="export-review-modal"
    >
      <div className="w-full max-w-2xl bg-[#0A0A0A] border-2 border-[#E4FF00]/60 rounded-md p-6 sm:p-10 shadow-[0_20px_80px_rgba(228,255,0,0.3)] relative">
        <div className="flex flex-col items-center text-center gap-4">
          {isPending && <Loader2 className="w-14 h-14 text-[#E4FF00] animate-spin" />}
          {isApproved && <ShieldCheck className="w-14 h-14 text-emerald-400" />}
          {isRejected && <XCircle className="w-14 h-14 text-red-400" />}
          <h2 className="text-2xl sm:text-3xl font-['Chivo'] font-black text-white leading-tight">
            {isPending && t('exp_pending_title')}
            {isApproved && t('exp_approved_title')}
            {isRejected && t('exp_rejected_title')}
          </h2>
          <p className="text-base sm:text-lg text-[#E4E4E7] leading-relaxed whitespace-pre-line max-w-xl">
            {isPending && t('exp_pending_body')}
            {isApproved && t('exp_approved_body').replace('{kind}', displayKind)}
            {isRejected && t('exp_rejected_body')}
          </p>

          <div className="w-full border-t border-white/10 mt-4 pt-4 flex items-center justify-between gap-4 flex-wrap">
            <span className="text-sm sm:text-base text-[#A1A1AA]">
              {t('exp_confirm_read')}
            </span>
            <button
              type="button"
              onClick={handleOui}
              disabled={sendingKey || downloading}
              data-testid="exp-review-oui"
              className="inline-flex items-center justify-center gap-2 px-8 py-3 bg-red-500 hover:bg-red-600 text-white rounded-sm font-['Chivo'] font-black text-base sm:text-lg tracking-wider transition disabled:opacity-60"
            >
              {(sendingKey || downloading) && <Loader2 className="w-4 h-4 animate-spin" />}
              {t('exp_confirm_yes')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
