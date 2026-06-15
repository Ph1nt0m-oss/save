const { useState, useEffect, useRef } = React;

const Calculator = () => {
  const [display, setDisplay] = useState('0');
  const [previousValue, setPreviousValue] = useState(null);
  const [operation, setOperation] = useState(null);
  const [waitingForNewValue, setWaitingForNewValue] = useState(false);
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const soundRef = useRef(null);

  useEffect(() => {
    const savedHistory = localStorage.getItem('calcHistory');
    if (savedHistory) {
      setHistory(JSON.parse(savedHistory));
    }
  }, []);

  const playSound = () => {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const now = audioContext.currentTime;
    const osc = audioContext.createOscillator();
    const gain = audioContext.createGain();
    osc.connect(gain);
    gain.connect(audioContext.destination);
    osc.frequency.setValueAtTime(800, now);
    osc.frequency.exponentialRampToValueAtTime(400, now + 0.1);
    gain.gain.setValueAtTime(0.3, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.1);
    osc.start(now);
    osc.stop(now + 0.1);
  };

  const handleNumberClick = (num) => {
    playSound();
    if (waitingForNewValue) {
      setDisplay(String(num));
      setWaitingForNewValue(false);
    } else {
      setDisplay(display === '0' ? String(num) : display + num);
    }
  };

  const handleDecimal = () => {
    playSound();
    if (!display.includes('.')) {
      setDisplay(display + '.');
      setWaitingForNewValue(false);
    }
  };

  const handleOperation = (op) => {
    playSound();
    const currentValue = parseFloat(display);

    if (previousValue === null) {
      setPreviousValue(currentValue);
    } else if (operation) {
      const result = performCalculation(previousValue, currentValue, operation);
      setDisplay(String(result));
      setPreviousValue(result);
    }

    setOperation(op);
    setWaitingForNewValue(true);
  };

  const performCalculation = (prev, current, op) => {
    switch (op) {
      case '+':
        return prev + current;
      case '−':
        return prev - current;
      case '×':
        return prev * current;
      case '÷':
        return current !== 0 ? prev / current : 0;
      case '%':
        return (prev * current) / 100;
      case '**':
        return Math.pow(prev, current);
      default:
        return current;
    }
  };

  const handleEquals = () => {
    playSound();
    if (operation && previousValue !== null) {
      const currentValue = parseFloat(display);
      const result = performCalculation(previousValue, currentValue, operation);
      const calculation = `${previousValue} ${operation} ${currentValue} = ${result}`;
      
      setDisplay(String(result));
      addToHistory(calculation);
      
      setPreviousValue(null);
      setOperation(null);
      setWaitingForNewValue(true);
    }
  };

  const addToHistory = (calculation) => {
    const newHistory = [{ id: Date.now(), calc: calculation }, ...history.slice(0, 19)];
    setHistory(newHistory);
    localStorage.setItem('calcHistory', JSON.stringify(newHistory));
  };

  const handleClear = () => {
    playSound();
    setDisplay('0');
    setPreviousValue(null);
    setOperation(null);
    setWaitingForNewValue(false);
  };

  const handleBackspace = () => {
    playSound();
    if (display.length > 1) {
      setDisplay(display.slice(0, -1));
    } else {
      setDisplay('0');
    }
  };

  const handleToggleSign = () => {
    playSound();
    const num = parseFloat(display);
    setDisplay(String(-num));
  };

  const handleSpecialFunction = (func) => {
    playSound();
    const num = parseFloat(display);
    let result = 0;

    switch (func) {
      case 'sqrt':
        result = Math.sqrt(num);
        break;
      case 'sin':
        result = Math.sin((num * Math.PI) / 180);
        break;
      case 'cos':
        result = Math.cos((num * Math.PI) / 180);
        break;
      case 'log':
        result = Math.log10(num);
        break;
      default:
        result = num;
    }

    setDisplay(String(result));
    addToHistory(`${func}(${num}) = ${result}`);
    setWaitingForNewValue(true);
  };

  const clearHistory = () => {
    setHistory([]);
    localStorage.removeItem('calcHistory');
  };

  const Button = ({ children, onClick, variant = 'default', className = '' }) => {
    const baseStyle = 'h-16 rounded-lg font-semibold text-lg transition-all duration-200 active:scale-95 select-none';
    const variants = {
      default: 'bg-[#0F0F13] hover:bg-[#1a1a22] text-white border border-[rgba(255,255,255,0.1)]',
      operation: 'bg-[#E4FF00] hover:bg-[#f0ff4d] text-[#050505] font-bold',
      equals: 'bg-[#00FF66] hover:bg-[#33ff88] text-[#050505] font-bold col-span-2',
      special: 'bg-[#00D4FF] hover:bg-[#33e5ff] text-[#050505] text-sm',
    };

    return (
      <button
        onClick={onClick}
        className={`${baseStyle} ${variants[variant]} ${className}`}
      >
        {children}
      </button>
    );
  };

  return (
    <div className="w-full h-screen bg-[#050505] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="mb-6 flex justify-between items-center">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-[#E4FF00] to-[#00FF66] bg-clip-text text-transparent">Calculatrice</h1>
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="p-2 rounded-lg bg-[#0F0F13] hover:bg-[#1a1a22] border border-[rgba(255,255,255,0.1)] transition-all duration-200"
            title="Historique"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </button>
        </div>

        {/* Main Calculator Card */}
        <div className="bg-[#0F0F13] rounded-2xl p-6 border border-[rgba(255,255,255,0.1)] shadow-2xl">
          {/* Display */}
          <div className="bg-[#050505] rounded-xl p-6 mb-6 border border-[rgba(228,255,0,0.2)] text-right overflow-hidden">
            <div className="text-gray-400 text-sm mb-2 min-h-6">{
              operation ? `${previousValue} ${operation}` : ''
            }</div>
            <div className="text-5xl font-bold text-[#E4FF00] break-words word-break overflow-ellipsis animate-fadeIn">
              {display.length > 12 ? parseFloat(display).toExponential(5) : display}
            </div>
          </div>

          {/* Quick Operations */}
          <div className="grid grid-cols-4 gap-2 mb-4">
            <Button variant="special" onClick={() => handleSpecialFunction('sqrt')}>√</Button>
            <Button variant="special" onClick={() => handleSpecialFunction('sin')}>sin</Button>
            <Button variant="special" onClick={() => handleSpecialFunction('cos')}>cos</Button>
            <Button variant="special" onClick={() => handleSpecialFunction('log')}>log</Button>
          </div>

          {/* Calculator Buttons */}
          <div className="grid grid-cols-4 gap-3">
            {/* Row 1 */}
            <Button onClick={handleClear} className="col-span-2 bg-red-600 hover:bg-red-700">AC</Button>
            <Button onClick={handleBackspace}>⌫</Button>
            <Button variant="operation" onClick={() => handleOperation('%')}>%</Button>

            {/* Row 2 */}
            <Button onClick={() => handleNumberClick(7)}>7</Button>
            <Button onClick={() => handleNumberClick(8)}>8</Button>
            <Button onClick={() => handleNumberClick(9)}>9</Button>
            <Button variant="operation" onClick={() => handleOperation('÷')}>÷</Button>

            {/* Row 3 */}
            <Button onClick={() => handleNumberClick(4)}>4</Button>
            <Button onClick={() => handleNumberClick(5)}>5</Button>
            <Button onClick={() => handleNumberClick(6)}>6</Button>
            <Button variant="operation" onClick={() => handleOperation('×')}>×</Button>

            {/* Row 4 */}
            <Button onClick={() => handleNumberClick(1)}>1</Button>
            <Button onClick={() => handleNumberClick(2)}>2</Button>
            <Button onClick={() => handleNumberClick(3)}>3</Button>
            <Button variant="operation" onClick={() => handleOperation('−')}>−</Button>

            {/* Row 5 */}
            <Button onClick={() => handleNumberClick(0)} className="col-span-2">0</Button>
            <Button onClick={handleDecimal}>,</Button>
            <Button variant="operation" onClick={() => handleOperation('+')}>+</Button>

            {/* Row 6 */}
            <Button variant="operation" onClick={() => handleOperation('**')} className="col-span-2">x^y</Button>
            <Button onClick={handleToggleSign} className="col-span-2">+/−</Button>

            {/* Equals */}
            <Button variant="equals" onClick={handleEquals}>=</Button>
          </div>
        </div>

        {/* History Panel */}
        {showHistory && (
          <div className="mt-6 bg-[#0F0F13] rounded-2xl p-6 border border-[rgba(255,255,255,0.1)] max-h-64 overflow-y-auto animate-slideUp">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-[#E4FF00]">Historique</h2>
              {history.length > 0 && (
                <button
                  onClick={clearHistory}
                  className="text-sm px-3 py-1 rounded bg-red-600 hover:bg-red-700 transition-colors"
                >
                  Effacer
                </button>
              )}
            </div>
            {history.length === 0 ? (
              <p className="text-gray-400 text-center py-4">Aucun calcul pour l'instant</p>
            ) : (
              <div className="space-y-2">
                {history.map((item) => (
                  <div
                    key={item.id}
                    className="bg-[#050505] p-3 rounded-lg border border-[rgba(255,255,255,0.1)] text-sm font-mono text-gray-300 hover:border-[#E4FF00] transition-colors cursor-pointer"
                    onClick={() => {
                      const result = item.calc.split(' = ')[1];
                      if (result) setDisplay(result);
                    }}
                  >
                    {item.calc}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<Calculator />);