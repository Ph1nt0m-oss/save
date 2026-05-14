import React, { useState } from 'react';
import { Bell } from 'lucide-react';
import DeviceManager from './DeviceManager';
import useDeviceIdentity from '../hooks/useDeviceIdentity';
import { useLanguage } from '../contexts/LanguageContext';

/**
 * Bell with a red counter — only visible to creator devices when pending
 * device requests exist. Clicking it opens the DeviceManager modal.
 */
export default function NotificationBell({ className = '' }) {
  const device = useDeviceIdentity();
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);

  if (!device.isCreatorView) return null;

  const count = device.pendingCount || 0;
  const title = count === 0
    ? t('nb_none')
    : count === 1
      ? t('nb_pending_one')
      : t('nb_pending_many').replace('{n}', String(count));
  return (
    <>
      <button
        type="button"
        onClick={() => { setOpen(true); }}
        data-testid="notification-bell"
        className={`relative inline-flex items-center justify-center w-9 h-9 rounded-sm border border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06] transition-colors ${className}`}
        title={title}
      >
        <Bell className="w-4 h-4" />
        {count > 0 && (
          <span
            data-testid="notification-bell-count"
            className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 flex items-center justify-center text-[10px] font-['Chivo'] font-bold text-white bg-red-500 rounded-full border border-[#050505]"
          >
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>
      <DeviceManager
        open={open}
        onClose={() => { setOpen(false); device.refresh(); }}
        role={device.role}
        currentKeyId={device.keyId}
      />
    </>
  );
}
