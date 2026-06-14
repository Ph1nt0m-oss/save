const { useEffect, useMemo, useRef, useState } = React;

function clsx(...parts) {
  return parts.filter(Boolean).join(" ");
}

function formatForDisplay(numStr) {
  if (numStr == null || numStr === "") return "0";
  if (numStr === "Erreur") return "Erreur";
  if (numStr === "∞" || numStr === "-∞") return numStr;
  // Supporte les nombres en notation scientifique
  if (/e/i.test(numStr)) {
    const [mant, exp] = numStr.split(/e/i);
    const mantNum = Number(mant);
    const mantFmt = Number.isFinite(mantNum) ? mantNum.toLocaleString("fr-FR", { maximumFractionDigits: 10 }) : mant;
    return `${mantFmt}e${exp}`;
  }
  // Limiter l'affichage pour éviter l'overflow tout en restant lisible
  const n = Number(numStr);
  if (Number.isFinite(n)) {
    const abs = Math.abs(n);
    if (abs !== 0 && (abs >= 1e12 || abs < 1e-9)) {
      return n.toExponential(6).replace("+", "");
    }
  }
  // Ajout de séparateurs de milliers si possible
  if (/^-?\d+(\.\d+)?$/.test(numStr)) {
    const [i, d] = numStr.split(".");
    const iFmt = Number(i).toLocaleString("fr-FR");
    return d != null ? `${iFmt}.${d}` : iFmt;
  }
  return String(numStr);
}

function sanitizeExpressionForPreview(tokens) {
  // Prévisualisation textuelle, sans évaluation
  return tokens
    .map((t) => {
      if (t.type === "number") return t.value;
      if (t.type === "op") return t.value;
      return "";
    })
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

function computeTokens(tokens) {
  // Algorithme: Shunting-yard vers RPN puis évaluation
  // Supporte + - × ÷ % et le signe unaire via nombres déjà signés.
  const prec = { "%": 2, "×": 2, "÷": 2, "+": 1, "-": 1 };

  const output = [];
  const ops = [];

  for (const t of tokens) {
    if (t.type === "number") {
      output.push(t);
    } else if (t.type === "op") {
      const o1 = t.value;
      while (ops.length) {
        const o2 = ops[ops.length - 1];
        if (o2.type !== "op") break;
        const top = o2.value;
        if ((prec[top] ?? 0) >= (prec[o1] ?? 0)) {
          output.push(ops.pop());
        } else {
          break;
        }
      }
      ops.push(t);
    }
  }
  while (ops.length) output.push(ops.pop());

  const stack = [];
  for (const t of output) {
    if (t.type === "number") {
      const v = Number(t.value);
      if (!Number.isFinite(v)) return { ok: false, value: "Erreur" };
      stack.push(v);
    } else {
      const op = t.value;
      const b = stack.pop();
      const a = stack.pop();
      if (a == null || b == null) return { ok: false, value: "Erreur" };
      let r;
      if (op === "+") r = a + b;
      else if (op === "-") r = a - b;
      else if (op === "×") r = a * b;
      else if (op === "÷") {
        if (b === 0) return { ok: false, value: "Erreur" };
        r = a / b;
      } else if (op === "%") {
        if (b === 0) return { ok: false, value: "Erreur" };
        r = a % b;
      } else return { ok: false, value: "Erreur" };

      if (!Number.isFinite(r)) return { ok: false, value: r === Infinity ? "∞" : r === -Infinity ? "-∞" : "Erreur" };
      stack.push(r);
    }
  }

  if (stack.length !== 1) return { ok: false, value: "Erreur" };

  const result = stack[0];
  // Convertir en string stable sans perdre trop de précision
  const s = Number.isInteger(result) ? String(result) : String(Number(result.toPrecision(14)));
  return { ok: true, value: s };
}

function App() {
  const STORAGE_KEY = "test_iter53_calc_state_v1";

  const [current, setCurrent] = useState("0");
  const [tokens, setTokens] = useState([]); // [{type:'number'|'op', value:string}]
  const [justEvaluated, setJustEvaluated] = useState(false);
  const [memory, setMemory] = useState(0);
  const [history, setHistory] = useState([]); // { expr, result, ts }
  const [toast, setToast] = useState(null); // {type, message}
  const [isOnline, setIsOnline] = useState(typeof navigator !== "undefined" ? navigator.onLine : true);

  const toastTimer = useRef(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === "object") {
          if (typeof parsed.current === "string") setCurrent(parsed.current);
          if (Array.isArray(parsed.tokens)) setTokens(parsed.tokens);
          if (typeof parsed.justEvaluated === "boolean") setJustEvaluated(parsed.justEvaluated);
          if (typeof parsed.memory === "number") setMemory(parsed.memory);
          if (Array.isArray(parsed.history)) setHistory(parsed.history.slice(0, 30));
        }
      }
    } catch (e) {
      // Si localStorage corrompu, on repart proprement
      setCurrent("0");
      setTokens([]);
      setJustEvaluated(false);
      setMemory(0);
      setHistory([]);
    }
  }, []);

  useEffect(() => {
    try {
      const payload = {
        current,
        tokens,
        justEvaluated,
        memory,
        history: history.slice(0, 30),
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch (e) {
      // Pas bloquant
    }
  }, [current, tokens, justEvaluated, memory, history]);

  useEffect(() => {
    const onOnline = () => setIsOnline(true);
    const onOffline = () => setIsOnline(false);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  useEffect(() => {
    if (!toast) return;
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2000);
    return () => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
    };
  }, [toast]);

  const preview = useMemo(() => {
    const expr = sanitizeExpressionForPreview([
      ...tokens,
      ...(current !== "" ? [{ type: "number", value: current }] : []),
    ]);
    return expr;
  }, [tokens, current]);

  function showToast(type, message) {
    setToast({ type, message });
  }

  function resetAll() {
    setCurrent("0");
    setTokens([]);
    setJustEvaluated(false);
    showToast("info", "Réinitialisé");
  }

  function backspace() {
    if (justEvaluated) {
      // Après un résultat, backspace remet en édition
      setJustEvaluated(false);
    }

    setCurrent((c) => {
      if (c === "Erreur") return "0";
      if (c.length <= 1) return "0";
      const next = c.slice(0, -1);
      if (next === "-" || next === "") return "0";
      return next;
    });
  }

  function inputDigit(d) {
    setCurrent((c) => {
      if (c === "Erreur") c = "0";
      if (justEvaluated) {
        setTokens([]);
        setJustEvaluated(false);
        return String(d);
      }
      if (c === "0") return String(d);
      if (c === "-0") return "-" + String(d);
      if (c.length >= 18) return c;
      return c + String(d);
    });
  }

  function inputDot() {
    setCurrent((c) => {
      if (c === "Erreur") c = "0";
      if (justEvaluated) {
        setTokens([]);
        setJustEvaluated(false);
        return "0.";
      }
      if (c.includes(".")) return c;
      if (c === "" || c === "0") return "0.";
      if (c === "-") return "-0.";
      return c + ".";
    });
  }

  function toggleSign() {
    setCurrent((c) => {
      if (c === "Erreur") return "0";
      if (justEvaluated) {
        setTokens([]);
        setJustEvaluated(false);
      }
      if (c === "0") return "-0";
      if (c === "-0") return "0";
      if (c.startsWith("-")) return c.slice(1);
      return "-" + c;
    });
  }

  function toNumberSafe(s) {
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  }

  function pushOperator(op) {
    if (current === "Erreur") {
      setCurrent("0");
      setTokens([]);
      setJustEvaluated(false);
      showToast("danger", "Expression invalide");
      return;
    }

    setTokens((prev) => {
      const next = [...prev];

      const cur = current;
      const curNum = toNumberSafe(cur);
      if (curNum == null) {
        showToast("danger", "Nombre invalide");
        return prev;
      }

      // Si on vient de calculer, on continue avec le résultat courant
      if (justEvaluated) setJustEvaluated(false);

      // Ajoute le nombre courant si dernier token n'est pas un nombre identique déjà ajouté
      // Règle simple : si le dernier token est un nombre, on le remplace
      if (next.length && next[next.length - 1].type === "number") {
        next[next.length - 1] = { type: "number", value: cur };
      } else {
        next.push({ type: "number", value: cur });
      }

      // Si un opérateur existe déjà en fin, on le remplace
      if (next.length && next[next.length - 1].type === "op") {
        next[next.length - 1] = { type: "op", value: op };
      } else {
        next.push({ type: "op", value: op });
      }

      return next;
    });

    setCurrent("0");
  }

  function evaluate() {
    if (current === "Erreur") {
      showToast("danger", "Corrigez l'erreur avant de continuer");
      return;
    }

    const curNum = toNumberSafe(current);
    if (curNum == null) {
      showToast("danger", "Nombre invalide");
      return;
    }

    const full = [...tokens];
    // Si l'expression se termine par un opérateur, on l'ignore et on calcule avec le dernier nombre
    if (full.length && full[full.length - 1].type === "op") {
      full.pop();
    }

    // Ajoute le nombre courant
    if (full.length && full[full.length - 1].type === "number") {
      full[full.length - 1] = { type: "number", value: current };
    } else {
      full.push({ type: "number", value: current });
    }

    // Doit alterner correctement
    if (!full.length) return;
    if (full.length === 1 && full[0].type === "number") {
      setCurrent(full[0].value);
      setTokens([]);
      setJustEvaluated(true);
      return;
    }

    // Nettoyage: supprimer doubles opérateurs éventuels
    const cleaned = [];
    for (const t of full) {
      const last = cleaned[cleaned.length - 1];
      if (t.type === "op" && last && last.type === "op") {
        cleaned[cleaned.length - 1] = t;
      } else {
        cleaned.push(t);
      }
    }
    if (cleaned[cleaned.length - 1]?.type === "op") cleaned.pop();

    const res = computeTokens(cleaned);
    const exprStr = sanitizeExpressionForPreview(cleaned);

    if (!res.ok) {
      setCurrent("Erreur");
      setTokens([]);
      setJustEvaluated(true);
      setHistory((h) => [{ expr: exprStr || "Expression", result: "Erreur", ts: Date.now() }, ...h].slice(0, 30));
      showToast("danger", "Calcul impossible");
      return;
    }

    setCurrent(res.value);
    setTokens([]);
    setJustEvaluated(true);
    setHistory((h) => [{ expr: exprStr || "Expression", result: res.value, ts: Date.now() }, ...h].slice(0, 30));
  }

  function percent() {
    // Convertit le courant en pourcentage (÷100)
    const n = toNumberSafe(current);
    if (n == null) {
      setCurrent("Erreur");
      showToast("danger", "Nombre invalide");
      return;
    }
    const v = n / 100;
    const s = Number.isInteger(v) ? String(v) : String(Number(v.toPrecision(14)));
    setCurrent(s);
    setJustEvaluated(false);
  }

  function sqrt() {
    const n = toNumberSafe(current);
    if (n == null) {
      setCurrent("Erreur");
      showToast("danger", "Nombre invalide");
      return;
    }
    if (n < 0) {
      setCurrent("Erreur");
      showToast("danger", "Racine carrée impossible");
      return;
    }
    const v = Math.sqrt(n);
    const s = Number.isInteger(v) ? String(v) : String(Number(v.toPrecision(14)));
    setCurrent(s);
    setJustEvaluated(true);
    setTokens([]);
  }

  function invert() {
    const n = toNumberSafe(current);
    if (n == null || n === 0) {
      setCurrent("Erreur");
      showToast("danger", "Division par zéro");
      return;
    }
    const v = 1 / n;
    const s = Number.isInteger(v) ? String(v) : String(Number(v.toPrecision(14)));
    setCurrent(s);
    setJustEvaluated(true);
    setTokens([]);
  }

  function memoryClear() {
    setMemory(0);
    showToast("info", "Mémoire effacée");
  }

  function memoryRecall() {
    const s = Number.isInteger(memory) ? String(memory) : String(Number(memory.toPrecision(14)));
    setCurrent(s);
    setJustEvaluated(false);
    showToast("info", "Mémoire rappelée");
  }

  function memoryAdd() {
    const n = toNumberSafe(current);
    if (n == null) {
      showToast("danger", "Nombre invalide");
      return;
    }
    setMemory((m) => m + n);
    showToast("success", "Ajouté à la mémoire");
  }

  function memorySub() {
    const n = toNumberSafe(current);
    if (n == null) {
      showToast("danger", "Nombre invalide");
      return;
    }
    setMemory((m) => m - n);
    showToast("success", "Soustrait de la mémoire");
  }

  function clearHistory() {
    setHistory([]);
    showToast("info", "Historique effacé");
  }

  useEffect(() => {
    function onKeyDown(e) {
      const k = e.key;
      if (k >= "0" && k <= "9") {
        e.preventDefault();
        inputDigit(k);
      } else if (k === "." || k === ",") {
        e.preventDefault();
        inputDot();
      } else if (k === "Enter" || k === "=") {
        e.preventDefault();
        evaluate();
      } else if (k === "Backspace") {
        e.preventDefault();
        backspace();
      } else if (k === "Escape") {
        e.preventDefault();
        resetAll();
      } else if (k === "+") {
        e.preventDefault();
        pushOperator("+");
      } else if (k === "-") {
        e.preventDefault();
        pushOperator("-");
      } else if (k === "*") {
        e.preventDefault();
        pushOperator("×");
      } else if (k === "/") {
        e.preventDefault();
        pushOperator("÷");
      } else if (k === "%") {
        e.preventDefault();
        pushOperator("%");
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [current, tokens, justEvaluated, memory]);

  function Button({ label, onClick, variant = "base", wide = false, ariaLabel }) {
    const base = "btn calc-press select-none";
    const styles = {
      base: "bg-[#0F0F13] border border-white/10 text-white hover:border-white/20",
      primary: "bg-[#E4FF00] text-black border border-[#E4FF00]/30 hover:shadow-[0_0_30px_rgba(228,255,0,0.25)]",
      accent: "bg-[#00D4FF]/15 text-white border border-white/10 hover:border-[#00D4FF]/40",
      secondary: "bg-[#00FF66]/15 text-white border border-white/10 hover:border-[#00FF66]/40",
      danger: "bg-red-500/15 text-white border border-white/10 hover:border-red-500/40",
      ghost: "bg-transparent border border-white/10 text-white hover:bg-white/5",
    };
    return (
      <button
        type="button"
        aria-label={ariaLabel || label}
        onClick={onClick}
        className={clsx(
          base,
          styles[variant] || styles.base,
          wide ? "col-span-2" : "",
          "rounded-xl px-4 py-4 sm:py-5 text-lg sm:text-xl font-semibold",
          "transition-all duration-200 ease-out",
          "active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-[#00D4FF]/50"
        )}
      >
        {label}
      </button>
    );
  }

  const memIndicator = useMemo(() => {
    return Math.abs(memory) > 0 ? "M" : "";
  }, [memory]);

  const displayValue = useMemo(() => formatForDisplay(current), [current]);

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-xl px-4 pt-6 pb-10">
        <header className="flex items-center justify-between gap-3 mb-4">
          <div className="flex flex-col">
            <div className="text-sm text-zinc-400">Calculatrice</div>
            <h1 className="text-xl font-bold tracking-tight">TEST_iter53</h1>
          </div>
          <div className="flex items-center gap-2">
            <span className={clsx(
              "text-xs px-2 py-1 rounded-full border",
              isOnline ? "border-[#00FF66]/30 bg-[#00FF66]/10 text-zinc-100" : "border-red-500/30 bg-red-500/10 text-zinc-100"
            )}>
              {isOnline ? "En ligne" : "Hors ligne"}
            </span>
            <button
              type="button"
              onClick={() => {
                try {
                  localStorage.removeItem(STORAGE_KEY);
                } catch (e) {}
                setCurrent("0");
                setTokens([]);
                setJustEvaluated(false);
                setMemory(0);
                setHistory([]);
                showToast("info", "Données locales effacées");
              }}
              className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-zinc-200 hover:bg-white/10 transition"
              aria-label="Effacer les données locales"
              title="Effacer les données locales"
            >
              Effacer
            </button>
          </div>
        </header>

        <main className="grid gap-4">
          <section className="card rounded-2xl border border-white/10 bg-[#0F0F13] shadow-lg">
            <div className="p-4 sm:p-5">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-zinc-400">Expression</span>
                  {memIndicator && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-[#E4FF00]/10 border border-[#E4FF00]/20 text-[#E4FF00]">
                      {memIndicator}
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={clearHistory}
                  className="text-xs text-zinc-400 hover:text-white transition"
                  aria-label="Effacer l'historique"
                >
                  Effacer l'historique
                </button>
              </div>

              <div className="min-h-[22px] text-sm text-zinc-400 truncate" aria-label="Aperçu de l'expression">
                {preview || "—"}
              </div>

              <div className="mt-2 flex items-end justify-between gap-3">
                <div className="flex-1">
                  <div
                    className={clsx(
                      "display text-right font-extrabold tracking-tight",
                      "text-4xl sm:text-5xl leading-none",
                      current === "Erreur" ? "text-red-300" : "text-white"
                    )}
                    aria-label="Affichage"
                  >
                    {displayValue}
                  </div>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-4 gap-3">
                <Button label="MC" variant="ghost" onClick={memoryClear} ariaLabel="Mémoire : effacer" />
                <Button label="MR" variant="ghost" onClick={memoryRecall} ariaLabel="Mémoire : rappeler" />
                <Button label="M+" variant="ghost" onClick={memoryAdd} ariaLabel="Mémoire : ajouter" />
                <Button label="M-" variant="ghost" onClick={memorySub} ariaLabel="Mémoire : soustraire" />
              </div>
            </div>

            <div className="px-4 sm:px-5 pb-5">
              <div className="grid grid-cols-4 gap-3">
                <Button label="AC" variant="danger" onClick={resetAll} ariaLabel="Tout effacer" />
                <Button label="⌫" variant="accent" onClick={backspace} ariaLabel="Retour arrière" />
                <Button label="±" variant="accent" onClick={toggleSign} ariaLabel="Changer le signe" />
                <Button label="÷" variant="secondary" onClick={() => pushOperator("÷")} ariaLabel="Diviser" />

                <Button label="7" onClick={() => inputDigit(7)} />
                <Button label="8" onClick={() => inputDigit(8)} />
                <Button label="9" onClick={() => inputDigit(9)} />
                <Button label="×" variant="secondary" onClick={() => pushOperator("×")} ariaLabel="Multiplier" />

                <Button label="4" onClick={() => inputDigit(4)} />
                <Button label="5" onClick={() => inputDigit(5)} />
                <Button label="6" onClick={() => inputDigit(6)} />
                <Button label="-" variant="secondary" onClick={() => pushOperator("-")} ariaLabel="Soustraire" />

                <Button label="1" onClick={() => inputDigit(1)} />
                <Button label="2" onClick={() => inputDigit(2)} />
                <Button label="3" onClick={() => inputDigit(3)} />
                <Button label="+" variant="secondary" onClick={() => pushOperator("+")} ariaLabel="Additionner" />

                <Button label="%" variant="accent" onClick={percent} ariaLabel="Pourcentage" />
                <Button label="0" onClick={() => inputDigit(0)} />
                <Button label="," variant="accent" onClick={inputDot} ariaLabel="Virgule décimale" />
                <Button label="=" variant="primary" onClick={evaluate} ariaLabel="Égal" />
              </div>

              <div className="mt-3 grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={sqrt}
                  className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-zinc-200 hover:bg-white/10 transition active:scale-[0.99] focus:outline-none focus:ring-2 focus:ring-[#00D4FF]/50"
                  aria-label="Racine carrée"
                >
                  √ Racine carrée
                </button>
                <button
                  type="button"
                  onClick={invert}
                  className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-zinc-200 hover:bg-white/10 transition active:scale-[0.99] focus:outline-none focus:ring-2 focus:ring-[#00D4FF]/50"
                  aria-label="Inverse"
                >
                  1/x Inverse
                </button>
              </div>

              <div className="mt-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-sm text-zinc-400">Historique (30 max)</div>
                  <div className="text-xs text-zinc-500">Persisté via LocalStorage</div>
                </div>
                <div className="max-h-44 overflow-auto pr-1 rounded-xl border border-white/10 bg-black/20">
                  {history.length === 0 ? (
                    <div className="p-4 text-sm text-zinc-400">Aucun calcul pour le moment.</div>
                  ) : (
                    <ul className="divide-y divide-white/10">
                      {history.map((h, idx) => (
                        <li
                          key={h.ts + "_" + idx}
                          className="p-3 hover:bg-white/5 transition cursor-pointer"
                          onClick={() => {
                            setCurrent(h.result);
                            setTokens([]);
                            setJustEvaluated(true);
                            showToast("info", "Résultat recopié");
                          }}
                          role="button"
                          tabIndex={0}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              setCurrent(h.result);
                              setTokens([]);
                              setJustEvaluated(true);
                              showToast("info", "Résultat recopié");
                            }
                          }}
                          aria-label={`Historique : ${h.expr} = ${h.result}`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="text-sm text-zinc-200 truncate">{h.expr}</div>
                              <div className="text-xs text-zinc-500">{new Date(h.ts).toLocaleString("fr-FR")}</div>
                            </div>
                            <div className="text-sm font-semibold text-[#E4FF00]">{formatForDisplay(h.result)}</div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          </section>

          <footer className="text-xs text-zinc-500 text-center">
            Astuces clavier : chiffres, +, -, *, /, %, Entrée (=), Retour arrière, Échap (AC)
          </footer>
        </main>
      </div>

      <div
        className={clsx(
          "fixed left-1/2 -translate-x-1/2 bottom-5 z-50",
          "transition-all duration-200",
          toast ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2 pointer-events-none"
        )}
        aria-live="polite"
        aria-label="Notification"
      >
        {toast && (
          <div
            className={clsx(
              "rounded-2xl border px-4 py-3 shadow-lg backdrop-blur",
              "bg-[#0F0F13]/80",
              toast.type === "success" && "border-[#00FF66]/30",
              toast.type === "danger" && "border-red-500/30",
              toast.type === "info" && "border-white/10"
            )}
          >
            <div className="text-sm text-zinc-100">{toast.message}</div>
          </div>
        )}
      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
