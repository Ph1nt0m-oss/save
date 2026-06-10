import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { X, UserPlus, Check, XCircle, Users, Key, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { withCreatorProof } from '../lib/deviceIdentity';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * iter82 C20 — Système d'amitié par clé. Permet à un user d'envoyer une
 * demande d'amitié à une clé (saisie manuelle = pseudo). Une fois acceptée,
 * les deux peuvent se DM via /messages/send avec target_key_id.
 *
 * La créatrice peut court-circuiter : sa demande est auto-acceptée.
 */
export default function FriendsPanel({ open, onClose }) {
  const [sent, setSent] = useState([]);
  const [received, setReceived] = useState([]);
  const [targetKey, setTargetKey] = useState('');
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    try {
      const body = await withCreatorProof(API, axios, {});
      const r = await axios.post(`${API}/friends/list`, body);
      setSent(r.data?.sent || []);
      setReceived(r.data?.received || []);
    } catch (_) { /* silent */ }
  };

  useEffect(() => {
    if (!open) return undefined;
    refresh();
    const id = setInterval(refresh, 6000);
    return () => clearInterval(id);
  }, [open]); // eslint-disable-line

  const sendRequest = async () => {
    const tk = targetKey.trim();
    if (!tk || busy) return;
    setBusy(true);
    try {
      const body = await withCreatorProof(API, axios, { target_key_id: tk });
      const r = await axios.post(`${API}/friends/request`, body);
      toast.success(r.data?.auto_accepted ? 'Ami accepté automatiquement (créa)' : 'Demande envoyée');
      setTargetKey('');
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Demande impossible');
    } finally {
      setBusy(false);
    }
  };

  const decide = async (request_id, accept) => {
    try {
      const body = await withCreatorProof(API, axios, { request_id, accept });
      await axios.post(`${API}/friends/decide`, body);
      toast.success(accept ? 'Ami accepté' : 'Refusé');
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Action impossible');
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[80] bg-black/40 backdrop-blur-sm" onClick={onClose} data-testid="friends-panel">
      <aside
        onClick={(e) => e.stopPropagation()}
        className="absolute top-0 right-0 bottom-0 w-full sm:w-[480px] bg-[#0A0A0A] border-l border-white/15 shadow-[-20px_0_60px_rgba(0,0,0,0.6)] flex flex-col overflow-hidden"
      >
        <header className="px-3 py-3 border-b border-white/10 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-[#E4FF00]" />
            <h2 className="text-sm font-['Chivo'] font-bold text-white">Amis & demandes</h2>
          </div>
          <button onClick={onClose} data-testid="friends-close" className="text-[#A1A1AA] hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </header>

        {/* Add a friend by key */}
        <div className="p-3 border-b border-white/10 space-y-2">
          <div className="text-[10px] uppercase tracking-widest text-[#A1A1AA] flex items-center gap-1">
            <Key className="w-3 h-3" /> Ajouter par clé d&apos;appareil
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={targetKey}
              onChange={(e) => setTargetKey(e.target.value)}
              placeholder="Clé publique de l'ami (key_id complet)"
              data-testid="friend-key-input"
              className="flex-1 px-3 py-2 bg-[#0F0F13] border border-white/15 rounded-sm text-xs focus:outline-none focus:border-[#E4FF00] font-mono"
            />
            <button
              onClick={sendRequest}
              disabled={!targetKey.trim() || busy}
              data-testid="friend-send-request"
              className="px-3 py-2 bg-[#E4FF00] text-[#050505] font-bold rounded-sm hover:bg-[#E4FF00]/90 disabled:opacity-40"
            >
              <UserPlus className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Received requests */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          <section>
            <h3 className="text-[10px] uppercase tracking-widest text-[#A1A1AA] mb-2">
              Demandes reçues ({received.filter((r) => r.status === 'pending').length})
            </h3>
            {received.filter((r) => r.status === 'pending').length === 0 && (
              <div className="text-[11px] text-[#71717A] py-2">Aucune demande en attente.</div>
            )}
            <div className="space-y-1.5">
              {received.filter((r) => r.status === 'pending').map((r) => (
                <div key={r.request_id} data-testid={`friend-req-${r.request_id}`} className="bg-black/30 border border-white/10 rounded-sm p-2 flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white font-bold truncate">{r.from_pseudo || r.from_key_id.slice(0, 14)}</div>
                    <div className="text-[10px] text-[#71717A] truncate font-mono">{r.from_key_id}</div>
                  </div>
                  <button onClick={() => decide(r.request_id, true)} data-testid={`friend-accept-${r.request_id}`} className="px-2 py-1 text-[11px] border border-emerald-400 text-emerald-300 rounded-sm hover:bg-emerald-400/10">
                    <Check className="w-3 h-3" />
                  </button>
                  <button onClick={() => decide(r.request_id, false)} data-testid={`friend-refuse-${r.request_id}`} className="px-2 py-1 text-[11px] border border-red-400 text-red-300 rounded-sm hover:bg-red-400/10">
                    <XCircle className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h3 className="text-[10px] uppercase tracking-widest text-[#A1A1AA] mb-2">
              Amis ({[...sent, ...received].filter((r) => r.status === 'accepted').length})
            </h3>
            <div className="space-y-1.5">
              {[...sent, ...received].filter((r) => r.status === 'accepted').map((r) => {
                const isSent = sent.includes(r);
                const peerKey = isSent ? r.to_key_id : r.from_key_id;
                const peerPseudo = isSent ? r.to_pseudo : r.from_pseudo;
                return (
                  <div key={r.request_id} className="bg-black/30 border border-emerald-500/20 rounded-sm p-2 flex items-center gap-2">
                    <Check className="w-3 h-3 text-emerald-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white font-bold truncate">{peerPseudo || peerKey?.slice(0, 14)}</div>
                      <div className="text-[10px] text-[#71717A] truncate font-mono">{peerKey}</div>
                    </div>
                  </div>
                );
              })}
            </div>
            {[...sent, ...received].filter((r) => r.status === 'accepted').length === 0 && (
              <div className="text-[11px] text-[#71717A] py-2">Pas encore d&apos;ami.</div>
            )}
          </section>

          <section>
            <h3 className="text-[10px] uppercase tracking-widest text-[#A1A1AA] mb-2 inline-flex items-center gap-1">
              <Clock className="w-3 h-3" /> Demandes envoyées ({sent.filter((r) => r.status === 'pending').length})
            </h3>
            <div className="space-y-1.5">
              {sent.filter((r) => r.status === 'pending').map((r) => (
                <div key={r.request_id} className="bg-black/30 border border-white/10 rounded-sm p-2">
                  <div className="text-sm text-white truncate">{r.to_pseudo || r.to_key_id?.slice(0, 14)}</div>
                  <div className="text-[10px] text-[#71717A] truncate font-mono">{r.to_key_id}</div>
                </div>
              ))}
              {sent.filter((r) => r.status === 'pending').length === 0 && (
                <div className="text-[11px] text-[#71717A] py-2">Aucune demande envoyée en attente.</div>
              )}
            </div>
          </section>
        </div>
      </aside>
    </div>
  );
}
