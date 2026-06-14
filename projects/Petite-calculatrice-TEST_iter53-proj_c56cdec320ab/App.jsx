const { useState, useEffect } = React;

const Calculator = () => {
  const [display, setDisplay] = useState('0');
  const [previousValue, setPreviousValue] = useState(null);
  const [operation, setOperation] = useState(null);
  const [waitingForNewValue, setWaitingForNewValue] = useState(false);
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  // Charger l'historique depuis localStorage au montage
  useEffect(() => {
    const savedHistory = localStorage.getItem('calculatorHistory');
    if (savedHistory) {
      try {
        setHistory(JSON.parse(savedHistory));
      } catch (e) {
        console.error('Erreur de chargement historique');
      }
    }
  }, []);

  // Sauvegarder l'historique dans localStorage
  useEffect(() => {
    localStorage.setItem('calculatorHistory', JSON.stringify(history));
  }, [history]);

  const handleNumber = (num) => {
    if (waitingForNewValue) {
      setDisplay(String(num));
      setWaitingForNewValue(false);
    } else {
      setDisplay(display === '0' ? String(num) : display + num);
    }
  };

  const handleDecimal = () => {
    if (waitingForNewValue) {
      setDisplay('0.');
      setWaitingForNewValue(false);
    } else if (!display.includes('.')) {
      setDisplay(display + '.');
    }
  };

  const handleOperation = (op) => {
    const currentValue = parseFloat(display);

    if (previousValue === null) {
      setPreviousValue(currentValue);
    } else if (operation) {
      const result = calculate(previousValue, currentValue, operation);
      setDisplay(String(result));
      setPreviousValue(result);
    }

    setOperation(op);
    setWaitingForNewValue(true);
  };

  const calculate = (prev, current, op) => {
    switch (op) {
      case '+':
        return prev + current;
      case '−':
        return prev - current;
      case '×':
        return prev * current;
      case '÷':
        return current === 0 ? 0 : prev / current;
      case '%':
        return (prev * current) / 100;
      case '^':
        return Math.pow(prev, current);
      default:
        return current;
    }
  };

  const handleEquals = () => {
    if (operation && previousValue !== null) {
      const currentValue = parseFloat(display);
      const result = calculate(previousValue, currentValue, operation);
      const formattedResult = Math.round(result * 100000000) / 100000000;
      const entry = `${previousValue} ${operation} ${currentValue} = ${formattedResult}`;
      
      setDisplay(String(formattedResult));
      setHistory([entry, ...history]);
      setPreviousValue(null);
      setOperation(null);
      setWaitingForNewValue(true);
    }
  };

  const handleClear = () => {
    setDisplay('0');
    setPreviousValue(null);
    setOperation(null);
    setWaitingForNewValue(false);
  };

  const handleBackspace = () => {
    if (display.length === 1) {
      setDisplay('0');
    } else {
      setDisplay(display.slice(0, -1));
    }
  };

  const handleToggleSign = () => {
    const value = parseFloat(display);
    setDisplay(String(-value));
  };

  const handleSqrt = () => {
    const value = parseFloat(display);
    const result = Math.sqrt(value);
    setDisplay(String(result));
  };

  const clearHistory = () => {
    setHistory([]);
  };

  const Button = ({ children, onClick, variant = 'default', className = '' }) => {
    const baseStyles = 'w-full h-16 rounded-lg font-semibold text-lg transition-all duration-200 active:scale-95 flex items-center justify-center';
    const variants = {
      default: 'bg-[#0F0F13] hover:bg-[#1A1A22] border border-[rgba(255,255,255,0.1)]',
      operator: 'bg-[#E4FF00] text-[#050505] hover:bg-[#F0FF4D] border border-[#E4FF00]',
      equals: 'bg-[#00FF66] text-[#050505] hover:bg-[#33FF88] border border-[#00FF66]',
      function: 'bg-[#00D4FF] text-[#050505] hover:bg-[#33E5FF] border border-[#00D4FF]',
      clear: 'bg-[#FF4444] text-white hover:bg-[#FF6666] border border-[#FF4444]'
    };

    return (
      <button
        onClick={onClick}
        className={`${baseStyles} ${variants[variant]} ${className}`}
      >
        {children}
      </button>
    );
  };

  const displayValue = display.length > 12 ? parseFloat(display).toExponential(6) : display;

  return (
    <div className="flex flex-col h-screen bg-[#050505] p-4 md:p-6 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-[#E4FF00] to-[#00FF66] bg-clip-text text-transparent">Calculatrice</h1>
          <p className="text-[#A1A1AA] text-sm mt-1">TEST_iter53</p>
        </div>
        <button
          onClick={() => setShowHistory(!showHistory)}
          className="relative p-3 bg-[#0F0F13] hover:bg-[#1A1A22] rounded-lg border border-[rgba(255,255,255,0.1)] transition-all duration-200"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {history.length > 0 && <span className="absolute top-1 right-1 w-2 h-2 bg-[#E4FF00] rounded-full"></span>}
        </button>
      </div>

      {/* Historique */}
      {showHistory && (
        <div className="bg-[#0F0F13] border border-[rgba(255,255,255,0.1)] rounded-lg p-4 max-h-48 overflow-y-auto animate-slideDown">
          <div className="flex justify-between items-center mb-3">
            <h2 className="font-semibold text-[#E4FF00]">Historique</h2>
            {history.length > 0 && (
              <button
                onClick={clearHistory}
                className="text-xs px-2 py-1 bg-[#FF4444] hover:bg-[#FF6666] rounded text-white transition-all"
              >
                Effacer
              </button>
            )}
          </div>
          {history.length === 0 ? (
            <p className="text-[#A1A1AA] text-sm">Aucun calcul sauvegardé</p>
          ) : (
            <div className="space-y-2">
              {history.map((item, index) => (
                <div key={index} className="text-sm text-[#A1A1AA] bg-[#050505] p-2 rounded border border-[rgba(255,255,255,0.05)] font-mono">
                  {item}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Écran */}
      <div className="bg-[#0F0F13] border-2 border-[rgba(228,255,0,0.3)] rounded-2xl p-6 shadow-[0_0_30px_rgba(228,255,0,0.2)] flex-1 flex flex-col justify-end min-h-32">
        <div className="text-right">
          {operation && previousValue !== null && (
            <div className="text-[#A1A1AA] text-sm mb-2 font-mono">
              {previousValue} {operation}
            </div>
          )}
          <div className="text-5xl md:text-6xl font-bold text-[#E4FF00] break-words">
            {displayValue}
          </div>
        </div>
      </div>

      {/* Clavier */}
      <div className="grid grid-cols-4 gap-2 md:gap-3">
        {/* Ligne 1 */}
        <Button onClick={handleClear} variant="clear" className="col-span-2">Effacer</Button>
        <Button onClick={handleBackspace} variant="function">←</Button>
        <Button onClick={() => handleOperation('÷')} variant="operator">÷</Button>

        {/* Ligne 2 */}
        <Button onClick={() => handleNumber(7)}>7</Button>
        <Button onClick={() => handleNumber(8)}>8</Button>
        <Button onClick={() => handleNumber(9)}>9</Button>
        <Button onClick={() => handleOperation('×')} variant="operator">×</Button>

        {/* Ligne 3 */}
        <Button onClick={() => handleNumber(4)}>4</Button>
        <Button onClick={() => handleNumber(5)}>5</Button>
        <Button onClick={() => handleNumber(6)}>6</Button>
        <Button onClick={() => handleOperation('−')} variant="operator">−</Button>

        {/* Ligne 4 */}
        <Button onClick={() => handleNumber(1)}>1</Button>
        <Button onClick={() => handleNumber(2)}>2</Button>
        <Button onClick={() => handleNumber(3)}>3</Button>
        <Button onClick={() => handleOperation('+')} variant="operator">+</Button>

        {/* Ligne 5 */}
        <Button onClick={() => handleNumber(0)} className="col-span-2">0</Button>
        <Button onClick={handleDecimal}>,</Button>
        <Button onClick={handleEquals} variant="equals">=</Button>
      </div>

      {/* Fonctions avancées */}
      <div className="grid grid-cols-4 gap-2 md:gap-3">
        <Button onClick={handleSqrt} variant="function">√</Button>
        <Button onClick={() => handleOperation('%')} variant="function">%</Button>
        <Button onClick={() => handleOperation('^')} variant="function">x^y</Button>
        <Button onClick={handleToggleSign} variant="function">±</Button>
      </div>

      {/* Footer */}
      <div className="text-center text-[#A1A1AA] text-xs mt-2">
        <p>Calculatrice TEST_iter53 • PWA Ready</p>
      </div>
    </div>
  );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<Calculator />);