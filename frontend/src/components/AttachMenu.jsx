import React, { useEffect, useRef, useState } from 'react';
import { Paperclip, Upload, ClipboardPaste, Link as LinkIcon, X, Loader2, FileText } from 'lucide-react';
import { toast } from 'sonner';
import { useLanguage } from '../contexts/LanguageContext';

/**
 * Paperclip attachment menu with three sources:
 *   - device:    file picker (any file type, single)
 *   - clipboard: read text or image from navigator.clipboard
 *   - url:       paste a URL (image/file link), the consumer fetches it
 *
 * Calls onResult({ kind: 'file'|'text'|'url', file?, text?, url?, name? }).
 * Visual: pill, opens an upward popover with three rows + dismiss.
 */
export default function AttachMenu({ onResult, disabled }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [showUrlInput, setShowUrlInput] = useState(false);
  const ref = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => {
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
        setShowUrlInput(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const pickFile = () => fileRef.current?.click();

  const onFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    onResult?.({ kind: 'file', file, name: file.name });
    setOpen(false);
    e.target.value = '';
  };

  const fromClipboard = async () => {
    setBusy(true);
    try {
      // Prefer rich items (image > text) when available.
      if (navigator.clipboard.read) {
        const items = await navigator.clipboard.read();
        for (const item of items) {
          const type = item.types.find(t => t.startsWith('image/'));
          if (type) {
            const blob = await item.getType(type);
            const file = new File([blob], `clipboard.${type.split('/')[1]}`, { type });
            onResult?.({ kind: 'file', file, name: file.name });
            setOpen(false);
            return;
          }
        }
      }
      const text = await navigator.clipboard.readText();
      if (text) {
        onResult?.({ kind: 'text', text });
      } else {
        toast.info(t('attach_clip_empty'));
      }
    } catch (err) {
      toast.error(t('attach_clip_fail'));
    } finally {
      setBusy(false);
      setOpen(false);
    }
  };

  const submitUrl = () => {
    const url = urlInput.trim();
    if (!url) return;
    try {
      // Basic validation — actually parse to fail fast on garbage.
      new URL(url);
    } catch (_) {
      toast.error(t('attach_url_invalid'));
      return;
    }
    onResult?.({ kind: 'url', url });
    setUrlInput('');
    setShowUrlInput(false);
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative flex-shrink-0">
      <input ref={fileRef} type="file" hidden onChange={onFile} data-testid="attach-file-input" />
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(o => !o)}
        data-testid="attach-btn"
        title={t('attach_title')}
        aria-label={t('attach_title')}
        className="inline-flex items-center justify-center h-11 w-11 rounded-sm border border-white/15 bg-white/[0.04] text-white hover:border-[#E4FF00]/50 hover:text-[#E4FF00] transition-all disabled:opacity-50"
      >
        <Paperclip className="w-4 h-4" />
      </button>

      {open && (
        <div
          data-testid="attach-menu"
          className="absolute bottom-full left-0 mb-2 w-72 bg-[#0A0A0A] border border-white/15 rounded-sm shadow-[0_8px_30px_rgba(0,0,0,0.6)] backdrop-blur-xl z-50"
        >
          <div className="flex items-center justify-between px-3 py-2 border-b border-white/10">
            <span className="text-xs text-[#A1A1AA] font-['Chivo'] font-bold uppercase tracking-wider">{t('attach_title')}</span>
            <button onClick={() => setOpen(false)} className="text-[#A1A1AA] hover:text-white">
              <X className="w-3 h-3" />
            </button>
          </div>

          {showUrlInput ? (
            <div className="p-3 space-y-2" data-testid="attach-url-form">
              <input
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && submitUrl()}
                placeholder="https://..."
                autoFocus
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/15 rounded-sm text-sm text-white placeholder-[#A1A1AA] focus:outline-none focus:border-[#E4FF00]/50"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => { setShowUrlInput(false); setUrlInput(''); }}
                  className="flex-1 px-3 py-2 text-xs text-[#A1A1AA] border border-white/10 rounded-sm hover:text-white"
                >
                  {t('cancel') || 'Annuler'}
                </button>
                <button
                  type="button"
                  onClick={submitUrl}
                  data-testid="attach-url-submit"
                  className="flex-1 px-3 py-2 text-xs font-bold bg-[#E4FF00] text-[#050505] rounded-sm"
                >
                  OK
                </button>
              </div>
            </div>
          ) : (
            <div className="py-1">
              <Row icon={Upload} testId="attach-from-device" onClick={pickFile} title={t('attach_device')} sub={t('attach_device_sub')} />
              <Row icon={ClipboardPaste} testId="attach-from-clipboard" onClick={fromClipboard} disabled={busy}
                   title={t('attach_clipboard')} sub={t('attach_clipboard_sub')} loading={busy} />
              <Row icon={LinkIcon} testId="attach-from-url" onClick={() => setShowUrlInput(true)}
                   title={t('attach_url')} sub={t('attach_url_sub')} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Row({ icon: Icon, title, sub, onClick, disabled, loading, testId }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      data-testid={testId}
      className="w-full text-left px-3 py-2.5 flex items-start gap-3 hover:bg-white/[0.05] transition-colors disabled:opacity-50"
    >
      {loading ? <Loader2 className="w-4 h-4 mt-0.5 text-[#E4FF00] animate-spin" /> : <Icon className="w-4 h-4 mt-0.5 text-[#E4FF00]" />}
      <span className="flex-1 min-w-0">
        <span className="block text-sm text-white font-['IBM_Plex_Sans']">{title}</span>
        <span className="block text-[11px] text-[#A1A1AA] mt-0.5 truncate">{sub}</span>
      </span>
      <FileText className="w-3 h-3 text-[#A1A1AA] mt-1.5 opacity-30" />
    </button>
  );
}
