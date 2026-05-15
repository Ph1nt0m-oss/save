import React, { useRef, useState, useEffect } from 'react';
import axios from 'axios';
import { Upload, ClipboardPaste, Smartphone, Monitor, Loader2, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const MAX_BYTES = 4 * 1024 * 1024;     // 4 MB
const MAX_DIM = 1600;                  // resize down before upload

/**
 * Mandatory device-info capture for the registration flow.
 * The user MUST drop / paste / pick a screenshot of their "About this
 * phone" or "About this PC" page. The image is OCR'd by Gemini Vision
 * (server-side via /api/auth/ocr-device-info) and the extracted
 * product/model/device_name is bubbled up via onChange.
 *
 * Display logic:
 *  - Phone → "Galaxy S21 5G" + "SM-G991U1" (two-line)
 *  - Computer → "DESKTOP-52KO8J1" (single line)
 *  - Unknown → red error + instructions to retake screenshot
 */
export default function DeviceCaptureField({ value, onChange, disabled }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);

  const downscaleToDataUrl = (file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = reject;
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const ratio = Math.min(1, MAX_DIM / Math.max(img.width, img.height));
        const w = Math.round(img.width * ratio);
        const h = Math.round(img.height * ratio);
        const canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        // JPEG keeps the payload small enough for the OCR endpoint
        resolve(canvas.toDataURL('image/jpeg', 0.85));
      };
      img.onerror = reject;
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });

  const submit = async (file) => {
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setError('Image trop lourde (>4 Mo). Compresse-la ou prends un format plus léger.');
      return;
    }
    if (!file.type.match(/^image\/(jpeg|png|webp)$/)) {
      setError('Format non supporté (JPEG/PNG/WebP uniquement).');
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const dataUrl = await downscaleToDataUrl(file);
      setPreview(dataUrl);
      const r = await axios.post(`${API}/auth/ocr-device-info`, { image_base64: dataUrl });
      const d = r.data || {};
      if (d.kind === 'phone' && (d.product || d.model)) {
        onChange?.({ kind: 'phone', product: d.product || '', model: d.model || '', device_name: '' });
        toast.success(`Détecté : ${d.product || d.model}`);
      } else if (d.kind === 'computer' && d.device_name) {
        onChange?.({ kind: 'computer', product: '', model: '', device_name: d.device_name });
        toast.success(`Détecté : ${d.device_name}`);
      } else {
        onChange?.(null);
        setError(
          "Impossible d'identifier l'appareil. Capture la page complète :\n" +
          "• Téléphone Android : Paramètres > À propos du téléphone (Nom du produit + Numéro de modèle visibles)\n" +
          "• iPhone : Réglages > Général > Informations\n" +
          "• Windows : Paramètres > Système > Informations système (Nom de l'appareil visible)\n" +
          "• Mac : Réglages Système > Général > Informations"
        );
      }
    } catch (e) {
      onChange?.(null);
      setError(e?.response?.data?.detail || 'Erreur lors de l\'analyse de la capture.');
    } finally { setBusy(false); }
  };

  const onFile = (e) => {
    const f = e.target.files?.[0];
    if (f) submit(f);
  };

  const onDrop = (e) => {
    e.preventDefault();
    if (disabled) return;
    const f = e.dataTransfer.files?.[0];
    if (f) submit(f);
  };

  // Listen for paste events on the field itself (Ctrl+V → image)
  useEffect(() => {
    if (disabled) return undefined;
    const handler = (e) => {
      const items = e.clipboardData?.items || [];
      for (const it of items) {
        if (it.kind === 'file' && it.type.startsWith('image/')) {
          const f = it.getAsFile();
          if (f) {
            e.preventDefault();
            submit(f);
            break;
          }
        }
      }
    };
    document.addEventListener('paste', handler);
    return () => document.removeEventListener('paste', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disabled]);

  const ok = !!value && value.kind && (
    (value.kind === 'phone' && (value.product || value.model)) ||
    (value.kind === 'computer' && value.device_name)
  );

  return (
    <div className="space-y-2">
      <label className="text-xs font-['Chivo'] font-bold text-white">
        Capture d'écran de ton appareil <span className="text-red-400">*</span>
      </label>
      <div
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); }}
        onClick={() => !disabled && !busy && inputRef.current?.click()}
        data-testid="device-capture-dropzone"
        className={`relative rounded-sm border-2 border-dashed transition-colors cursor-pointer ${
          ok ? 'border-emerald-400/60 bg-emerald-500/5' :
          error ? 'border-red-400/60 bg-red-500/5' :
          'border-white/15 bg-black/30 hover:border-[#E4FF00]/40'
        } ${disabled || busy ? 'opacity-60 pointer-events-none' : ''}`}
      >
        <input ref={inputRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={onFile} className="hidden" data-testid="device-capture-input" />
        {busy ? (
          <div className="p-6 flex items-center justify-center gap-2 text-[#E4FF00]">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-xs">Analyse en cours…</span>
          </div>
        ) : ok ? (
          <div className="p-3 flex items-center gap-3" data-testid="device-capture-ok">
            <CheckCircle className="w-5 h-5 text-emerald-400 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              {value.kind === 'phone' ? (
                <>
                  <Smartphone className="w-3 h-3 inline-block mr-1 text-emerald-300" />
                  <span className="text-sm font-['Chivo'] font-bold text-white">{value.product || value.model}</span>
                  {value.product && value.model && value.product !== value.model && (
                    <div className="text-[11px] text-emerald-300 font-['IBM_Plex_Mono'] mt-0.5">{value.model}</div>
                  )}
                </>
              ) : (
                <>
                  <Monitor className="w-3 h-3 inline-block mr-1 text-emerald-300" />
                  <span className="text-sm font-['Chivo'] font-bold text-white">{value.device_name}</span>
                </>
              )}
            </div>
            <button type="button" onClick={(e) => { e.stopPropagation(); onChange?.(null); setPreview(null); setError(null); inputRef.current.value = ''; }}
              className="text-[11px] text-[#A1A1AA] hover:text-red-300" data-testid="device-capture-reset">
              Recommencer
            </button>
          </div>
        ) : (
          <div className="p-6 text-center">
            <Upload className="w-6 h-6 text-[#A1A1AA] mx-auto mb-2" />
            <p className="text-xs text-[#A1A1AA]">Glisse-dépose, clique pour parcourir ou colle (Ctrl+V) une capture.</p>
            <div className="flex items-center justify-center gap-3 mt-2 text-[10px] text-[#71717A]">
              <span className="inline-flex items-center gap-1"><Smartphone className="w-3 h-3" />Téléphone : « À propos »</span>
              <span className="inline-flex items-center gap-1"><Monitor className="w-3 h-3" />PC : « Informations système »</span>
              <span className="inline-flex items-center gap-1"><ClipboardPaste className="w-3 h-3" />Ctrl+V</span>
            </div>
          </div>
        )}
      </div>
      {preview && !ok && error && (
        <details className="text-[11px]">
          <summary className="text-[#A1A1AA] cursor-pointer">Voir la capture envoyée</summary>
          <img src={preview} alt="capture" className="max-h-40 rounded-sm border border-white/10 mt-1" />
        </details>
      )}
      {error && (
        <div className="text-xs text-red-300 flex items-start gap-2 whitespace-pre-line" data-testid="device-capture-error">
          <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {!error && !ok && (
        <p className="text-[10px] text-[#71717A] leading-snug">
          Cette capture sécurise les demandes d'accès et la clé. <strong>Téléphone</strong> : Paramètres &gt; À propos du téléphone (le « Nom du produit » et le « Numéro de modèle » doivent être visibles). <strong>Ordinateur</strong> : Paramètres &gt; Système &gt; Informations système (« Nom de l'appareil » visible).
        </p>
      )}
    </div>
  );
}
