import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Play, Loader2, Copy, Check, Paperclip, X as XIcon } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

/**
 * Bloc de code avec bouton Copier + bouton Exécuter (si langage Python).
 * Le résultat d'exécution s'affiche sous le bloc.
 */
function CodeBlock({ language, code, replSessionId }) {
  const [copied, setCopied] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null); // { stdout, stderr, exit_code, timed_out, duration_ms, images, variables }
  const [uploadedFiles, setUploadedFiles] = useState([]); // [{filename, data_base64}]
  const fileInputRef = React.useRef(null);

  const isPython = /^(py|python|python3)$/i.test(language || '');

  const doCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      toast.error('Copie impossible');
    }
  };

  const onFilePicked = async (e) => {
    const files = Array.from(e.target.files || []);
    const max = 10 * 1024 * 1024; // 10 MB
    const processed = [];
    for (const f of files.slice(0, 4)) {
      if (f.size > max) { toast.error(`${f.name} > 10 Mo`); continue; }
      const buf = await f.arrayBuffer();
      const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
      processed.push({ filename: f.name, data_base64: b64 });
    }
    setUploadedFiles((prev) => [...prev, ...processed].slice(0, 6));
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeFile = (i) => setUploadedFiles((prev) => prev.filter((_, idx) => idx !== i));

  const doRun = async () => {
    setRunning(true);
    setResult(null);
    try {
      const payload = { code, timeout_sec: 15 };
      if (replSessionId) payload.session_id = replSessionId;
      if (uploadedFiles.length) payload.files = uploadedFiles;
      const res = await axios.post(`${API}/sandbox/python`, payload, { withCredentials: true });
      setResult(res.data);
    } catch (e) {
      setResult({
        stdout: '',
        stderr: e?.response?.data?.detail || e?.message || 'Erreur sandbox',
        exit_code: -1,
        timed_out: false,
        duration_ms: 0,
      });
    } finally {
      setRunning(false);
    }
  };

  return (
    <div data-testid="chat-code-block" className="relative group my-3 rounded-sm overflow-hidden border border-white/10 bg-[#0A0A0A]">
      <div className="flex items-center justify-between px-3 py-1.5 bg-white/[0.04] border-b border-white/10">
        <span className="text-[11px] uppercase tracking-widest text-[#A1A1AA] font-['IBM_Plex_Sans']">
          {language || 'code'}
        </span>
        <div className="flex items-center gap-1.5">
          {isPython && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={onFilePicked}
                className="hidden"
                data-testid="code-file-input"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                data-testid="code-attach-btn"
                className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-sm bg-white/[0.04] text-[#A1A1AA] hover:bg-white/[0.08] hover:text-white border border-white/10 transition-colors"
                title="Joindre un fichier (CSV, JSON, image…) au cwd du sandbox"
              >
                <Paperclip className="w-3 h-3" />
                {uploadedFiles.length > 0 ? `${uploadedFiles.length} fichier${uploadedFiles.length > 1 ? 's' : ''}` : 'Joindre'}
              </button>
              <button
                type="button"
                onClick={doRun}
                disabled={running}
                data-testid="code-run-btn"
                className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-sm bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 border border-emerald-500/30 transition-colors disabled:opacity-60"
                title="Exécuter dans le sandbox Python"
              >
                {running ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                {running ? 'Exécution…' : 'Exécuter'}
              </button>
            </>
          )}
          <button
            type="button"
            onClick={doCopy}
            data-testid="code-copy-btn"
            className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-sm bg-white/[0.04] text-[#A1A1AA] hover:bg-white/[0.08] hover:text-white border border-white/10 transition-colors"
            title="Copier le code"
          >
            {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            {copied ? 'Copié' : 'Copier'}
          </button>
        </div>
      </div>
      <SyntaxHighlighter
        language={(language || 'text').toLowerCase()}
        style={oneDark}
        customStyle={{ margin: 0, padding: '12px 14px', fontSize: 13, background: 'transparent' }}
        wrapLongLines
      >
        {code}
      </SyntaxHighlighter>
      {uploadedFiles.length > 0 && (
        <div className="px-3 py-1.5 border-t border-white/10 bg-white/[0.02] flex flex-wrap gap-1.5" data-testid="code-attach-chips">
          {uploadedFiles.map((f, i) => (
            <span key={i} className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-sm bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 font-mono">
              <Paperclip className="w-2.5 h-2.5" />
              {f.filename}
              <button type="button" onClick={() => removeFile(i)} className="text-cyan-300/70 hover:text-white ml-0.5" title="Retirer">
                <XIcon className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      {result && (
        <div data-testid="code-run-output" className="border-t border-white/10 bg-black/40 p-3 text-[12.5px] font-mono">
          <div className="text-[11px] uppercase tracking-widest text-emerald-400 mb-1.5">
            ▶ Résultat {result.timed_out ? '⏱️ (timeout)' : ''} — {result.duration_ms} ms — exit {result.exit_code}
          </div>
          {result.stdout && (
            <pre className="whitespace-pre-wrap text-white/90 leading-relaxed">{result.stdout}</pre>
          )}
          {result.stderr && (
            <pre className="whitespace-pre-wrap text-red-300/90 leading-relaxed mt-2">{result.stderr}</pre>
          )}
          {result.images && result.images.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {result.images.map((img, i) => (
                <img
                  key={i}
                  src={`data:${img.mime_type || 'image/png'};base64,${img.data_base64}`}
                  alt={`Graphique ${i + 1}`}
                  data-testid={`code-run-image-${i}`}
                  className="max-w-full rounded-sm border border-white/10"
                />
              ))}
            </div>
          )}
          {result.variables && result.variables.length > 0 && (
            <div className="mt-3 border-t border-white/10 pt-2" data-testid="code-run-variables">
              <div className="text-[10px] uppercase tracking-widest text-purple-300 mb-1">
                ◆ Variables ({result.variables.length}) — persistantes (REPL)
              </div>
              <div className="flex flex-wrap gap-1">
                {result.variables.map((v, i) => (
                  <span key={i} className="text-[11px] px-1.5 py-0.5 rounded-sm bg-purple-500/10 border border-purple-500/20 text-purple-200 font-mono" title={v.repr}>
                    <span className="text-white">{v.name}</span>
                    <span className="text-purple-300/70">: {v.type}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Rendu riche du message IA : markdown + GFM (tables, listes) + syntax highlight
 * + bouton Exécuter sur les blocs Python. Pour les messages utilisateur on reste simple.
 */
export default function MessageContent({ content, isUser = false, replSessionId = null }) {
  if (isUser) {
    return <p className="whitespace-pre-wrap">{content}</p>;
  }
  return (
    <div className="cf-md leading-relaxed text-[14px]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ inline, className, children, ...props }) {
            const raw = String(children || '').replace(/\n$/, '');
            const match = /language-(\w+)/.exec(className || '');
            const lang = match ? match[1] : '';
            if (inline) {
              return (
                <code className="px-1.5 py-0.5 rounded-sm bg-white/[0.08] text-[#E4FF00] text-[0.88em]" {...props}>
                  {children}
                </code>
              );
            }
            return <CodeBlock language={lang} code={raw} replSessionId={replSessionId} />;
          },
          p({ children }) { return <p className="my-2">{children}</p>; },
          ul({ children }) { return <ul className="my-2 ml-5 list-disc space-y-1">{children}</ul>; },
          ol({ children }) { return <ol className="my-2 ml-5 list-decimal space-y-1">{children}</ol>; },
          h1({ children }) { return <h1 className="text-lg font-bold mt-3 mb-2">{children}</h1>; },
          h2({ children }) { return <h2 className="text-base font-bold mt-3 mb-2">{children}</h2>; },
          h3({ children }) { return <h3 className="text-sm font-bold mt-2 mb-1.5 uppercase tracking-wide">{children}</h3>; },
          strong({ children }) { return <strong className="text-white font-['Chivo'] font-bold">{children}</strong>; },
          a({ children, href }) {
            return <a href={href} target="_blank" rel="noreferrer" className="text-[#E4FF00] underline hover:text-[#F4FF33]">{children}</a>;
          },
          blockquote({ children }) {
            return <blockquote className="border-l-2 border-[#E4FF00]/50 pl-3 my-2 text-[#D4D4D8] italic">{children}</blockquote>;
          },
          table({ children }) {
            return <div className="overflow-x-auto my-2"><table className="min-w-full border border-white/10 text-[13px]">{children}</table></div>;
          },
          th({ children }) { return <th className="px-2 py-1 bg-white/[0.04] border border-white/10 text-left">{children}</th>; },
          td({ children }) { return <td className="px-2 py-1 border border-white/10">{children}</td>; },
          hr() { return <hr className="my-3 border-white/10" />; },
          img({ src, alt }) {
            return <img src={src} alt={alt || 'figure'} className="my-2 max-w-full rounded-sm border border-white/10" />;
          },
        }}
      >
        {content || ''}
      </ReactMarkdown>
    </div>
  );
}
