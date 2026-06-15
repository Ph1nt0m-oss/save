const { useEffect, useMemo, useRef, useState } = React;

function clampHistory(items, max = 30) {
  return items.slice(0, max);
}

function formatNumberForDisplay(str) {
  if (str === '' || str === null || str === undefined) return '';
  if (str === 'Erreur') return 'Erreur';
  if (str === 'Infinity' || str === '-Infinity') return 'Erreur';
  if (str === 'NaN') return 'Erreur';

  // Préserver les états intermédiaires (ex: "-", "0.")
  if (str === '-' || /^-?\d+\.$/.test(str)) return str;

  const n = Number(str);
  if (!Number.isFinite(n)) return 'Erreur';

  const abs = Math.abs(n);
  // Formatage lisible sans casser la précision (limite raisonnable)
  const useCompact = abs >= 1e12 || (abs > 0 && abs < 1e-9);
  if (useCompact) {
    return n.toExponential(6).replace(/\.?(0+)e/, 'e');
  }

  // Affichage avec séparateurs FR, sans forcer des décimales
  const parts = String(n).split('.');
  const intPart = Number(parts[0]).toLocaleString('fr-FR');
  if (parts.length === 1) return intPart;

  // Éviter les traînées de flottants
  let dec = parts[1];
  dec = dec.replace(/0+$/, '');
  if (dec.length === 0) return intPart;
  return `${intPart},${dec}`;
}

function normalizeDecimalInput(ch) {
  return ch === ',' ? '.' : ch;
}

function safeEvalBinary(aStr, op, bStr) {
  const a = Number(aStr);
  const b = Number(bStr);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return { ok: false, value: 'Erreur' };

  let res;
  switch (op) {
    case '+': res = a + b; break;
    case '−':
    case '-': res = a - b; break;
    case '×':
    case '*': res = a * b; break;
    case '÷':
    case '/':
      if (b === 0) return { ok: false, value: 'Erreur' };
      res = a / b;
      break;
    default:
      return { ok: false, value: 'Erreur' };
  }
  if (!Number.isFinite(res)) return { ok: false, value: 'Erreur' };

  // Limiter bruit flottant (mais sans trop tronquer)
  const rounded = Number.parseFloat(res.toPrecision(14));
  if (!Number.isFinite(rounded)) return { ok: false, value: 'Erreur' };
  return { ok: true, value: String(rounded) };
}

function isDigit(ch) {
  return /^[0-9]$/.test(ch);
}

function computePercent(currentStr, baseStr, op) {
  // Comportement type calculatrice:
  // Si un opérateur existe: b devient (a * b / 100)
  // Sinon: valeur devient valeur / 100
  const cur = Number(currentStr);
  if (!Number.isFinite(cur)) return 'Erreur';

  if (op && baseStr !== '' && baseStr !== '-') {
    const base = Number(baseStr);
    if (!Number.isFinite(base)) return 'Erreur';
    const v = (base * cur) / 100;
    const rounded = Number.parseFloat(v.toPrecision(14));
    return String(rounded);
  }

  const v = cur / 100;
  const rounded = Number.parseFloat(v.toPrecision(14));
  return String(rounded);
}

function App() {
  const STORAGE_KEY = 'test_iter53_calc_state_v1';

  const [display, setDisplay] = useState('0');
  const [a, setA] = useState('');
  const [op, setOp] = useState('');
  const [b, setB] = useState('');
  const [justEvaluated, setJustEvaluated] = useState(false);
  const [history, setHistory] = useState([]);
  const [toast, setToast] = useState({ open: false, text: '' });
  const [activeKey, setActiveKey] = useState('');

  const toastTimer = useRef(null);

  const displayPretty = useMemo(() => {
    if (display === 'Erreur') return 'Erreur';
    // Afficher virgule pour l'UI si décimal
    const formatted = formatNumberForDisplay(display);
    return formatted;
  }, [display]);

  function showToast(text) {
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    setToast({ open: true, text });
    toastTimer.current = window.setTimeout(() => setToast({ open: false, text: '' }), 1700);
  }

  function persist(next) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch (_) {
      // Silencieux: stockage non disponible
    }
  }

  function snapshotState(nextOverrides = {}) {
    const snap = {
      display,
      a,
      op,
      b,
      justEvaluated,
      history,
      ...nextOverrides
    };
    return snap;
  }

  useEffect(() => {
    // Chargement initial
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        if (typeof parsed.display === 'string') setDisplay(parsed.display);
        if (typeof parsed.a === 'string') setA(parsed.a);
        if (typeof parsed.op === 'string') setOp(parsed.op);
        if (typeof parsed.b === 'string') setB(parsed.b);
        if (typeof parsed.justEvaluated === 'boolean') setJustEvaluated(parsed.justEvaluated);
        if (Array.isArray(parsed.history)) setHistory(parsed.history);
      }
    } catch (_) {
      // Ignore
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // Persistance
    persist(snapshotState());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [display, a, op, b, justEvaluated, history]);

  useEffect(() => {
    function onKeyDown(e) {
      const key = e.key;
      const lower = String(key).toLowerCase();

      // Éviter le scroll sur espace
      if (key === ' ') e.preventDefault();

      let handled = true;

      if (isDigit(key)) {
        pressDigit(key);
        flashKey(key);
      } else if (key === '.' || key === ',') {
        pressDecimal('.');
        flashKey('decimal');
      } else if (key === 'Enter' || key === '=') {
        pressEquals();
        flashKey('=');
      } else if (key === 'Backspace') {
        pressBackspace();
        flashKey('backspace');
      } else if (key === 'Escape') {
        pressClearAll();
        flashKey('ac');
      } else if (key === '%') {
        pressPercent();
        flashKey('%');
      } else if (key === '+') {
        pressOperator('+');
        flashKey('+');
      } else if (key === '-') {
        pressOperator('−');
        flashKey('−');
      } else if (key === '*' || lower === 'x') {
        pressOperator('×');
        flashKey('×');
      } else if (key === '/') {
        pressOperator('÷');
        flashKey('÷');
      } else {
        handled = false;
      }

      if (handled) e.preventDefault();
    }

    window.addEventListener('keydown', onKeyDown, { passive: false });
    return () => window.removeEventListener('keydown', onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [a, b, op, display, justEvaluated]);

  function flashKey(k) {
    setActiveKey(k);
    window.setTimeout(() => setActiveKey(''), 120);
  }

  function currentTarget() {
    if (!op) return 'a';
    return 'b';
  }

  function setCurrentValue(nextStr) {
    if (!op) {
      setA(nextStr);
      setDisplay(nextStr === '' ? '0' : nextStr);
    } else {
      setB(nextStr);
      setDisplay(nextStr === '' ? '0' : nextStr);
    }
  }

  function pressDigit(d) {
    if (display === 'Erreur') {
      setA(''); setOp(''); setB('');
      setJustEvaluated(false);
    }

    // Si on vient d'évaluer et qu'on n'a pas choisi d'opérateur: nouveau calcul
    if (justEvaluated && !op) {
      setA(d);
      setDisplay(d);
      setJustEvaluated(false);
      return;
    }

    const tgt = currentTarget();
    const cur = tgt === 'a' ? a : b;

    // Gérer "0" initial
    if (cur === '0') {
      setCurrentValue(d);
      return;
    }

    // Si cur est vide ou "-" seul
    if (cur === '' || cur === '-') {
      setCurrentValue(cur + d);
      return;
    }

    // Limite de longueur
    if (cur.replace('-', '').replace('.', '').length >= 18) {
      showToast('Nombre trop long');
      return;
    }

    setCurrentValue(cur + d);
  }

  function pressDecimal(ch) {
    if (display === 'Erreur') {
      setA(''); setOp(''); setB('');
      setJustEvaluated(false);
    }

    if (justEvaluated && !op) {
      setA('0.');
      setDisplay('0.');
      setJustEvaluated(false);
      return;
    }

    const dot = normalizeDecimalInput(ch);
    const tgt = currentTarget();
    const cur = tgt === 'a' ? a : b;

    if (cur.includes('.')) return;

    if (cur === '' || cur === '-') {
      setCurrentValue((cur === '-' ? '-0.' : '0.'));
      return;
    }

    setCurrentValue(cur + dot);
  }

  function pressToggleSign() {
    if (display === 'Erreur') return;

    const tgt = currentTarget();
    const cur = tgt === 'a' ? a : b;

    if (justEvaluated && !op) {
      // Inverser le résultat
      const v = Number(display);
      if (!Number.isFinite(v)) {
        setDisplay('Erreur');
        setA(''); setOp(''); setB('');
        setJustEvaluated(false);
        return;
      }
      const next = String(Number.parseFloat((-v).toPrecision(14)));
      setA(next);
      setDisplay(next);
      setJustEvaluated(false);
      return;
    }

    if (cur === '') {
      setCurrentValue('-');
      return;
    }

    if (cur === '-') {
      setCurrentValue('');
      return;
    }

    if (cur.startsWith('-')) {
      setCurrentValue(cur.slice(1));
    } else {
      setCurrentValue('-' + cur);
    }
  }

  function pressOperator(nextOp) {
    if (display === 'Erreur') {
      setDisplay('0');
      setA('');
      setB('');
      setOp('');
      setJustEvaluated(false);
    }

    // Si on vient d'évaluer, on continue avec le résultat comme a
    if (justEvaluated) {
      setOp(nextOp);
      setB('');
      setJustEvaluated(false);
      return;
    }

    // Si a est vide mais display est un nombre: prendre display
    if (a === '' && display !== '0') {
      setA(display);
    }

    // Si op existe et b est prêt, calculer en chaîne
    if (op && b !== '' && b !== '-') {
      const left = a === '' ? '0' : a;
      const { ok, value } = safeEvalBinary(left, op, b);
      if (!ok) {
        setDisplay('Erreur');
        setA(''); setB(''); setOp('');
        setJustEvaluated(false);
        return;
      }
      setHistory(prev => clampHistory([
        { id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random(), expr: `${left} ${op} ${b}`, result: value, ts: Date.now() },
        ...prev
      ]));
      setA(value);
      setDisplay(value);
      setB('');
      setOp(nextOp);
      return;
    }

    // Si b est juste "-" (signe en cours), ne pas valider
    if (b === '-') {
      showToast('Terminez le nombre');
      return;
    }

    // Remplacer l'opérateur
    setOp(nextOp);
  }

  function pressEquals() {
    if (display === 'Erreur') return;

    const left = a === '' ? (op ? '0' : display) : a;

    if (!op) {
      // Rien à calculer
      if (left !== '' && left !== '-') {
        setDisplay(left);
        setA(left);
        setJustEvaluated(true);
      }
      return;
    }

    let right = b;

    // Répéter le dernier b si vide (comportement courant)
    if (right === '' || right === '-') {
      if (right === '-') {
        showToast('Terminez le nombre');
        return;
      }
      // Si b vide, réutiliser a (ex: 5 + = => 10)
      right = left;
    }

    const { ok, value } = safeEvalBinary(left, op, right);
    if (!ok) {
      setDisplay('Erreur');
      setA(''); setB(''); setOp('');
      setJustEvaluated(false);
      return;
    }

    setHistory(prev => clampHistory([
      { id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random(), expr: `${left} ${op} ${right}`, result: value, ts: Date.now() },
      ...prev
    ]));

    setDisplay(value);
    setA(value);
    setB('');
    setOp('');
    setJustEvaluated(true);
  }

  function pressBackspace() {
    if (display === 'Erreur') {
      pressClearAll();
      return;
    }

    if (justEvaluated && !op) {
      // Revenir à l'édition du résultat
      setJustEvaluated(false);
    }

    const tgt = currentTarget();
    const cur = tgt === 'a' ? a : b;

    if (cur === '') {
      // Si b vide et op existe, supprimer op
      if (tgt === 'b' && op) {
        setOp('');
        setDisplay(a === '' ? '0' : a);
      }
      return;
    }

    const next = cur.slice(0, -1);
    setCurrentValue(next);
  }

  function pressClearEntry() {
    if (display === 'Erreur') {
      pressClearAll();
      return;
    }

    if (!op) {
      setA('');
      setDisplay('0');
      setJustEvaluated(false);
      return;
    }

    setB('');
    setDisplay('0');
    setJustEvaluated(false);
  }

  function pressClearAll() {
    setDisplay('0');
    setA('');
    setOp('');
    setB('');
    setJustEvaluated(false);
  }

  function pressPercent() {
    if (display === 'Erreur') return;

    const tgt = currentTarget();
    const cur = tgt === 'a' ? a : b;

    if (cur === '' || cur === '-') {
      showToast('Aucune valeur à convertir');
      return;
    }

    const next = computePercent(cur, a === '' ? display : a, op);
    if (next === 'Erreur') {
      setDisplay('Erreur');
      setA(''); setB(''); setOp('');
      setJustEvaluated(false);
      return;
    }
    setCurrentValue(next);
  }

  function pressCopy() {
    const toCopy = display === 'Erreur' ? '' : display;
    if (!toCopy) {
      showToast('Rien à copier');
      return;
    }
    if (!navigator.clipboard || !window.isSecureContext) {
      // Fallback minimal
      try {
        const ta = document.createElement('textarea');
        ta.value = toCopy;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.top = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('Copié');
      } catch (_) {
        showToast('Copie indisponible');
      }
      return;
    }
    navigator.clipboard.writeText(toCopy).then(
      () => showToast('Copié'),
      () => showToast('Copie refusée')
    );
  }

  function pressHistoryItem(item) {
    setDisplay(item.result);
    setA(item.result);
    setOp('');
    setB('');
    setJustEvaluated(true);
    showToast('Résultat chargé');
  }

  function clearHistory() {
    setHistory([]);
    showToast('Historique effacé');
  }

  const keys = [
    { k: 'ac', label: 'AC', tone: 'muted', onPress: pressClearAll, aria: 'Tout effacer (AC)' },
    { k: 'ce', label: 'CE', tone: 'muted', onPress: pressClearEntry, aria: 'Effacer la saisie (CE)' },
    { k: 'backspace', label: '⌫', tone: 'muted', onPress: pressBackspace, aria: 'Retour arrière' },
    { k: '÷', label: '÷', tone: 'op', onPress: () => pressOperator('÷'), aria: 'Diviser' },

    { k: '7', label: '7', tone: 'num', onPress: () => pressDigit('7'), aria: '7' },
    { k: '8', label: '8', tone: 'num', onPress: () => pressDigit('8'), aria: '8' },
    { k: '9', label: '9', tone: 'num', onPress: () => pressDigit('9'), aria: '9' },
    { k: '×', label: '×', tone: 'op', onPress: () => pressOperator('×'), aria: 'Multiplier' },

    { k: '4', label: '4', tone: 'num', onPress: () => pressDigit('4'), aria: '4' },
    { k: '5', label: '5', tone: 'num', onPress: () => pressDigit('5'), aria: '5' },
    { k: '6', label: '6', tone: 'num', onPress: () => pressDigit('6'), aria: '6' },
    { k: '−', label: '−', tone: 'op', onPress: () => pressOperator('−'), aria: 'Soustraire' },

    { k: '1', label: '1', tone: 'num', onPress: () => pressDigit('1'), aria: '1' },
    { k: '2', label: '2', tone: 'num', onPress: () => pressDigit('2'), aria: '2' },
    { k: '3', label: '3', tone: 'num', onPress: () => pressDigit('3'), aria: '3' },
    { k: '+', label: '+', tone: 'op', onPress: () => pressOperator('+'), aria: 'Additionner' },

    { k: '%', label: '%', tone: 'muted', onPress: pressPercent, aria: 'Pourcentage' },
    { k: '0', label: '0', tone: 'numWide', onPress: () => pressDigit('0'), aria: '0' },
    { k: 'decimal', label: ',', tone: 'num', onPress: () => pressDecimal('.'), aria: 'Virgule décimale' },
    { k: '=', label: '=', tone: 'eq', onPress: pressEquals, aria: 'Égal' }
  ];

  function toneClasses(tone, isActive) {
    const base = 'calc-btn';
    const active = isActive ? ' calc-btn-active' : '';
    if (tone === 'op') return base + ' calc-btn-op' + active;
    if (tone === 'eq') return base + ' calc-btn-eq' + active;
    if (tone === 'muted') return base + ' calc-btn-muted' + active;
    if (tone === 'numWide') return base + ' calc-btn-num calc-btn-wide' + active;
    return base + ' calc-btn-num' + active;
  }

  const exprLine = useMemo(() => {
    const left = a !== '' ? a : '0';
    const right = b;
    if (!op) {
      if (justEvaluated) return 'Résultat';
      return 'Prêt';
    }
    if (right === '') return `${formatNumberForDisplay(left)} ${op}`;
    return `${formatNumberForDisplay(left)} ${op} ${formatNumberForDisplay(right)}`;
  }, [a, b, op, justEvaluated]);

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-4 sm:p-6">
      <div className="w-full max-w-[980px] grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-4 sm:gap-6">
        <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#0F0F13] shadow-lg shadow-[0_0_30px_rgba(228,255,0,0.18)]">
          <div className="absolute -top-24 -left-24 w-64 h-64 rounded-full blur-3xl opacity-25 bg-[#E4FF00]"></div>
          <div className="absolute -bottom-24 -right-24 w-72 h-72 rounded-full blur-3xl opacity-20 bg-[#00D4FF]"></div>

          <header className="relative z-10 p-4 sm:p-5 border-b border-white/10">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <h1 className="text-sm sm:text-base font-semibold tracking-wide">TEST_iter53</h1>
                <p className="text-xs text-zinc-400">Calculatrice moderne • Persistance locale</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={pressCopy}
                  className="px-3 py-2 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 active:scale-[0.98] transition"
                  aria-label="Copier le résultat"
                >
                  <span className="text-xs sm:text-sm text-zinc-200">Copier</span>
                </button>
                <button
                  onClick={pressToggleSign}
                  className="px-3 py-2 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 active:scale-[0.98] transition"
                  aria-label="Inverser le signe"
                  title="Inverser le signe (±)"
                >
                  <span className="text-xs sm:text-sm text-[#00FF66] font-semibold">±</span>
                </button>
              </div>
            </div>
          </header>

          <div className="relative z-10 p-4 sm:p-5">
            <div className="rounded-2xl border border-white/10 bg-[#050505] p-4 sm:p-5">
              <div className="flex items-center justify-between gap-3">
                <div className="text-xs text-zinc-400 truncate" aria-label="Expression en cours">{exprLine}</div>
                <div className="text-[10px] text-zinc-500 hidden sm:block">Entrée clavier activée</div>
              </div>
              <div className="mt-2 sm:mt-3 flex items-end justify-end">
                <div
                  className="text-right font-semibold tabular-nums leading-none select-text"
                  style={{ fontSize: displayPretty.length > 14 ? '1.6rem' : displayPretty.length > 10 ? '2.1rem' : '2.6rem' }}
                  aria-label="Affichage"
                >
                  {displayPretty || '0'}
                </div>
              </div>
            </div>

            <div className="mt-4 sm:mt-5 grid grid-cols-4 gap-2 sm:gap-3">
              {keys.map((it) => (
                <button
                  key={it.k}
                  onClick={it.onPress}
                  className={toneClasses(it.tone, activeKey === it.k)}
                  aria-label={it.aria}
                >
                  {it.label}
                </button>
              ))}
            </div>

            <div className="mt-4 sm:mt-5 flex flex-wrap items-center justify-between gap-2">
              <div className="text-xs text-zinc-400">
                Astuce: <span className="text-zinc-200">Échap</span>=AC, <span className="text-zinc-200">Entrée</span>=, <span className="text-zinc-200">⌫</span>=retour
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={clearHistory}
                  className="px-3 py-2 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 active:scale-[0.98] transition"
                  aria-label="Effacer l'historique"
                >
                  <span className="text-xs sm:text-sm text-zinc-200">Effacer l'historique</span>
                </button>
              </div>
            </div>
          </div>

          <div className={"toast " + (toast.open ? "toast-open" : "toast-closed")} role="status" aria-live="polite">
            <div className="toast-inner">{toast.text}</div>
          </div>
        </div>

        <aside className="rounded-2xl border border-white/10 bg-[#0F0F13] shadow-lg overflow-hidden">
          <div className="p-4 sm:p-5 border-b border-white/10 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm sm:text-base font-semibold">Historique</h2>
              <p className="text-xs text-zinc-400">Touchez une ligne pour réutiliser le résultat</p>
            </div>
            <div className="inline-flex items-center gap-2">
              <span className="text-xs px-2 py-1 rounded-lg border border-white/10 bg-white/5 text-zinc-300">
                {history.length} élément{history.length > 1 ? 's' : ''}
              </span>
            </div>
          </div>

          <div className="p-2 sm:p-3">
            {history.length === 0 ? (
              <div className="p-4 sm:p-6 rounded-xl border border-white/10 bg-[#050505]">
                <div className="text-sm text-zinc-200">Aucun calcul enregistré</div>
                <div className="mt-1 text-xs text-zinc-400">Vos opérations apparaîtront ici et seront conservées sur cet appareil.</div>
              </div>
            ) : (
              <div className="space-y-2 max-h-[520px] overflow-auto pr-1 calc-scroll">
                {history.map((h) => (
                  <button
                    key={h.id}
                    onClick={() => pressHistoryItem(h)}
                    className="w-full text-left p-3 sm:p-4 rounded-xl border border-white/10 bg-[#050505] hover:bg-white/5 active:scale-[0.995] transition"
                    aria-label={`Reprendre le résultat ${h.result}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-xs text-zinc-400 truncate">{h.expr.replaceAll('.', ',')}</div>
                        <div className="mt-1 text-base sm:text-lg font-semibold tabular-nums text-white">
                          {formatNumberForDisplay(h.result)}
                        </div>
                      </div>
                      <div className="shrink-0">
                        <div className="px-2 py-1 rounded-lg bg-white/5 border border-white/10 text-[10px] text-zinc-300">
                          Charger
                        </div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="p-4 sm:p-5 border-t border-white/10">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="rounded-xl border border-white/10 bg-[#050505] p-3">
                <div className="text-xs text-zinc-400">Persistance</div>
                <div className="mt-1 text-sm text-zinc-200">LocalStorage</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-[#050505] p-3">
                <div className="text-xs text-zinc-400">Mode hors-ligne</div>
                <div className="mt-1 text-sm text-zinc-200">PWA + Service Worker</div>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
