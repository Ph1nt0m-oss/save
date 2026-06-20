import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { MessageCircle } from 'lucide-react';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { withCreatorProof } from '../lib/deviceIdentity';
import MessagesPanel from './MessagesPanel';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Header button — pollable badge for unread message count.
 *
 *  - `inline`: compact text + icon, used in headers.
 *  - `icon`: just the bell-style icon with badge — used in app headers.
 *  - `floating`: legacy FAB (kept for now but not mounted globally).
 */
export default function MessageButton({ variant = 'icon' }) {
  const device = useDeviceIdentity();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (!device.keyId) return undefined;
    let cancelled = false;
    const tick = async () => {
      try {
        const body = await withCreatorProof(API, axios, {});
        const r = await axios.post(`${API}/messages/unread-count`, body);
        if (!cancelled) setUnread(r.data?.unread || 0);
      } catch (_) { /* ignore */ }
    };
    tick();
    const id = setInterval(tick, 10000);
    return () => { cancelled = true; clearInterval(id); };
  }, [device.keyId]);

  // For the legacy floating + inline variants we still hide the button until
  // the device identity is ready (those variants assume an authenticated UX).
  // The header icon variant renders immediately so visitors never see a
  // "missing" button while the device key is being provisioned in the
  // background.
  if (variant !== 'icon' && !device.keyId) return null;

  if (variant === 'icon') {
    return (
      <>
        <button
          type="button"
          onClick={() => setOpen(true)}
          data-testid="message-creator-icon-btn"
          title="Messages"
          className="relative inline-flex items-center justify-center w-9 h-9 rounded-sm bg-white/[0.04] border border-white/10 text-[#A1A1AA] hover:text-[#E4FF00] hover:border-[#E4FF00]/40 transition-colors"
        >
          <MessageCircle className="w-4 h-4" />
          {unread > 0 && (
            <span className="absolute -top-1 -right-1 min-w-[16px] h-[16px] bg-[#E4FF00] text-[#050505] text-[9px] font-bold rounded-full inline-flex items-center justify-center px-1">
              {unread}
            </span>
          )}
        </button>
        <MessagesPanel
          open={open}
          onClose={() => setOpen(false)}
          isCreator={device.role === 'creator'}
          currentKeyId={device.keyId}
        />
      </>
    );
  }

  if (variant === 'inline') {
    return (
      <>
        <button
          type="button"
          onClick={() => setOpen(true)}
          data-testid="message-creator-inline-btn"
          className="inline-flex items-center gap-1.5 text-[11px] text-[#E4FF00]/80 hover:text-[#E4FF00] font-['IBM_Plex_Sans'] transition-colors"
        >
          <MessageCircle className="w-3.5 h-3.5" />
          {device.role === 'creator' ? 'Messages reçus' : (device.staff_kind ? 'Messages staff' : 'Contacter un modo')}
          {unread > 0 && (
            <span className="text-[9px] bg-[#E4FF00] text-[#050505] font-bold px-1.5 rounded-full">{unread}</span>
          )}
        </button>
        <MessagesPanel
          open={open}
          onClose={() => setOpen(false)}
          isCreator={device.role === 'creator'}
          currentKeyId={device.keyId}
        />
      </>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-testid="message-creator-floating-btn"
        title="Messages"
        className="fixed bottom-4 right-4 z-[55] inline-flex items-center justify-center w-12 h-12 bg-[#E4FF00] hover:bg-white text-[#050505] rounded-full shadow-[0_10px_30px_rgba(228,255,0,0.4)] transition-all"
      >
        <MessageCircle className="w-5 h-5" />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] bg-red-500 text-white text-[10px] font-bold rounded-full inline-flex items-center justify-center px-1">
            {unread}
          </span>
        )}
      </button>
      <MessagesPanel
        open={open}
        onClose={() => setOpen(false)}
        isCreator={device.role === 'creator'}
        currentKeyId={device.keyId}
      />
    </>
  );
}
