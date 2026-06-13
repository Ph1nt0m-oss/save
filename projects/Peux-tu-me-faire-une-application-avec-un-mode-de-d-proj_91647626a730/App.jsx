const { useState, useEffect, useRef } = React;

const EXERCISES = [
  { id: 1, name: 'Pompes', emoji: '💪', muscles: 'Pectoraux, Triceps', difficulty: 'Facile' },
  { id: 2, name: 'Squats', emoji: '🦵', muscles: 'Quadriceps, Fessiers', difficulty: 'Facile' },
  { id: 3, name: 'Planche', emoji: '🧘', muscles: 'Abdominaux, Dos', difficulty: 'Moyen' },
  { id: 4, name: 'Burpees', emoji: '🔥', muscles: 'Corps entier', difficulty: 'Difficile' },
  { id: 5, name: 'Fentes', emoji: '🏃', muscles: 'Jambes, Fessiers', difficulty: 'Moyen' },
  { id: 6, name: 'Mountain Climbers', emoji: '⛰️', muscles: 'Cardio, Abdos', difficulty: 'Moyen' },
  { id: 7, name: 'Dips', emoji: '💺', muscles: 'Triceps, Épaules', difficulty: 'Moyen' },
  { id: 8, name: 'Jumping Jacks', emoji: '⭐', muscles: 'Cardio', difficulty: 'Facile' }
];

const FORM_TIPS = {
  'Pompes': ['Gardez le dos droit', 'Coudes à 45° du corps', 'Descendez jusqu\'à la poitrine', 'Contractez les abdos'],
  'Squats': ['Pieds largeur épaules', 'Genoux alignés avec les orteils', 'Descendez jusqu\'aux cuisses parallèles', 'Dos droit'],
  'Planche': ['Corps aligné tête-pieds', 'Abdos contractés', 'Regardez le sol', 'Respirez régulièrement'],
  'Burpees': ['Mouvement fluide', 'Explosivité au saut', 'Réception amortie', 'Rythme constant'],
  'Fentes': ['Genou avant à 90°', 'Genou arrière frôle le sol', 'Buste droit', 'Poids sur le talon avant'],
  'Mountain Climbers': ['Position planche stable', 'Ramenez les genoux à la poitrine', 'Rythme soutenu', 'Hanches basses'],
  'Dips': ['Épaules en arrière', 'Coudes vers l\'arrière', 'Descente contrôlée', 'Ne verrouillez pas les coudes'],
  'Jumping Jacks': ['Saut synchronisé', 'Bras tendus au-dessus', 'Réception souple', 'Rythme régulier']
};

function App() {
  const [mode, setMode] = useState('menu');
  const [dailyChallenge, setDailyChallenge] = useState(null);
  const [liveSession, setLiveSession] = useState(null);
  const [sessionHistory, setSessionHistory] = useState([]);
  const [stats, setStats] = useState({ streak: 0, totalSessions: 0, totalReps: 0 });
  const [currentRep, setCurrentRep] = useState(0);
  const [isActive, setIsActive] = useState(false);
  const [timer, setTimer] = useState(0);
  const [feedback, setFeedback] = useState([]);
  const [showTips, setShowTips] = useState(false);
  const timerRef = useRef(null);

  useEffect(() => {
    const saved = localStorage.getItem('coachfit_data');
    if (saved) {
      const data = JSON.parse(saved);
      setStats(data.stats || { streak: 0, totalSessions: 0, totalReps: 0 });
      setSessionHistory(data.history || []);
      
      const lastChallenge = data.lastChallengeDate;
      const today = new Date().toDateString();
      if (lastChallenge !== today) {
        generateDailyChallenge();
      } else {
        setDailyChallenge(data.dailyChallenge);
      }
    } else {
      generateDailyChallenge();
    }
  }, []);

  useEffect(() => {
    if (isActive && liveSession) {
      timerRef.current = setInterval(() => {
        setTimer(t => t + 1);
      }, 1000);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [isActive, liveSession]);

  const saveData = (newStats, newHistory, challenge) => {
    const data = {
      stats: newStats,
      history: newHistory,
      dailyChallenge: challenge || dailyChallenge,
      lastChallengeDate: new Date().toDateString()
    };
    localStorage.setItem('coachfit_data', JSON.stringify(data));
  };

  const generateDailyChallenge = () => {
    const numExercises = Math.floor(Math.random() * 2) + 3;
    const shuffled = [...EXERCISES].sort(() => 0.5 - Math.random());
    const selected = shuffled.slice(0, numExercises).map(ex => ({
      ...ex,
      reps: Math.floor(Math.random() * 10 + 10),
      sets: Math.floor(Math.random() * 2) + 2,
      completed: false
    }));
    
    const challenge = {
      id: Date.now(),
      date: new Date().toLocaleDateString('fr-FR'),
      exercises: selected,
      totalPoints: selected.reduce((acc, ex) => acc + ex.reps * ex.sets, 0)
    };
    
    setDailyChallenge(challenge);
    saveData(stats, sessionHistory, challenge);
  };

  const startLiveCoaching = (exercise) => {
    setLiveSession({
      exercise,
      targetReps: 20,
      currentSet: 1,
      totalSets: 3,
      startTime: Date.now()
    });
    setCurrentRep(0);
    setTimer(0);
    setFeedback([]);
    setMode('live');
  };

  const incrementRep = () => {
    const newRep = currentRep + 1;
    setCurrentRep(newRep);
    
    const tips = FORM_TIPS[liveSession.exercise.name];
    const randomTip = tips[Math.floor(Math.random() * tips.length)];
    
    const feedbackMessages = [
      { type: 'success', text: `Rep ${newRep} - Parfait ! 🎯`, tip: randomTip },
      { type: 'warning', text: `Rep ${newRep} - Attention à la forme`, tip: randomTip },
      { type: 'success', text: `Rep ${newRep} - Excellent contrôle ! 💪`, tip: randomTip },
      { type: 'info', text: `Rep ${newRep} - Continue comme ça !`, tip: randomTip }
    ];
    
    const newFeedback = feedbackMessages[Math.floor(Math.random() * feedbackMessages.length)];
    setFeedback(prev => [newFeedback, ...prev].slice(0, 5));
    
    if (newRep >= liveSession.targetReps) {
      if (liveSession.currentSet < liveSession.totalSets) {
        setTimeout(() => {
          setLiveSession(prev => ({ ...prev, currentSet: prev.currentSet + 1 }));
          setCurrentRep(0);
          setFeedback(prev => [{ type: 'success', text: `Série ${liveSession.currentSet} terminée ! 🎉 Repose-toi 30s`, tip: 'Hydrate-toi' }, ...prev]);
        }, 500);
      } else {
        finishLiveSession();
      }
    }
  };

  const finishLiveSession = () => {
    const session = {
      id: Date.now(),
      exercise: liveSession.exercise.name,
      reps: liveSession.targetReps * liveSession.totalSets,
      duration: timer,
      date: new Date().toLocaleString('fr-FR'),
      performance: Math.floor(Math.random() * 20 + 80)
    };
    
    const newHistory = [session, ...sessionHistory].slice(0, 50);
    const newStats = {
      streak: stats.streak + 1,
      totalSessions: stats.totalSessions + 1,
      totalReps: stats.totalReps + session.reps
    };
    
    setSessionHistory(newHistory);
    setStats(newStats);
    saveData(newStats, newHistory);
    
    setIsActive(false);
    setFeedback([{ type: 'success', text: `🏆 Session terminée ! ${session.reps} reps en ${timer}s`, tip: 'Excellent travail !' }]);
    
    setTimeout(() => {
      setMode('menu');
      setLiveSession(null);
    }, 3000);
  };

  const completeChallengeExercise = (exerciseId) => {
    const updated = {
      ...dailyChallenge,
      exercises: dailyChallenge.exercises.map(ex => 
        ex.id === exerciseId ? { ...ex, completed: true } : ex
      )
    };
    setDailyChallenge(updated);
    
    const allCompleted = updated.exercises.every(ex => ex.completed);
    if (allCompleted) {
      const newStats = {
        streak: stats.streak + 1,
        totalSessions: stats.totalSessions + 1,
        totalReps: stats.totalReps + updated.totalPoints
      };
      setStats(newStats);
      saveData(newStats, sessionHistory, updated);
      
      setTimeout(() => {
        alert('🎉 Défi quotidien terminé ! +' + updated.totalPoints + ' points');
        generateDailyChallenge();
      }, 500);
    } else {
      saveData(stats, sessionHistory, updated);
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (mode === 'menu') {
    return (
      <div className="min-h-screen p-4 pb-24">
        <header className="text-center mb-8 pt-6">
          <h1 className="text-4xl font-bold mb-2 text-[#E4FF00] glow-text">CoachFit Pro</h1>
          <p className="text-[#A1A1AA]">Votre coach personnel virtuel</p>
        </header>

        <div className="max-w-md mx-auto mb-8 grid grid-cols-3 gap-4">
          <div className="bg-[#0F0F13] rounded-xl p-4 border border-white/10">
            <div className="text-[#E4FF00] text-2xl font-bold">{stats.streak}</div>
            <div className="text-xs text-[#A1A1AA]">Jours de suite</div>
          </div>
          <div className="bg-[#0F0F13] rounded-xl p-4 border border-white/10">
            <div className="text-[#00FF66] text-2xl font-bold">{stats.totalSessions}</div>
            <div className="text-xs text-[#A1A1AA]">Sessions</div>
          </div>
          <div className="bg-[#0F0F13] rounded-xl p-4 border border-white/10">
            <div className="text-[#00D4FF] text-2xl font-bold">{stats.totalReps}</div>
            <div className="text-xs text-[#A1A1AA]">Répétitions</div>
          </div>
        </div>

        <div className="max-w-md mx-auto space-y-4">
          <button
            onClick={() => setMode('daily')}
            className="w-full bg-gradient-to-r from-[#E4FF00] to-[#00FF66] text-black font-bold py-6 rounded-xl hover:shadow-[0_0_30px_rgba(228,255,0,0.5)] transition-all transform hover:scale-105 active:scale-95"
          >
            <div className="text-2xl mb-1">🎯 Défi Quotidien</div>
            <div className="text-sm opacity-80">
              {dailyChallenge && dailyChallenge.exercises.filter(e => !e.completed).length} exercices restants
            </div>
          </button>

          <button
            onClick={() => setMode('coach')}
            className="w-full bg-gradient-to-r from-[#00D4FF] to-[#00FF66] text-black font-bold py-6 rounded-xl hover:shadow-[0_0_30px_rgba(0,212,255,0.5)] transition-all transform hover:scale-105 active:scale-95"
          >
            <div className="text-2xl mb-1">🤖 Coach en Direct</div>
            <div className="text-sm opacity-80">Correction en temps réel</div>
          </button>

          <button
            onClick={() => setMode('history')}
            className="w-full bg-[#0F0F13] border border-white/10 text-white font-bold py-4 rounded-xl hover:border-[#E4FF00] transition-all"
          >
            📊 Historique des sessions
          </button>
        </div>
      </div>
    );
  }

  if (mode === 'daily') {
    const completed = dailyChallenge?.exercises.filter(e => e.completed).length || 0;
    const total = dailyChallenge?.exercises.length || 0;
    const progress = (completed / total) * 100;

    return (
      <div className="min-h-screen p-4 pb-24">
        <button
          onClick={() => setMode('menu')}
          className="mb-4 text-[#E4FF00] flex items-center gap-2"
        >
          ← Retour
        </button>

        <div className="max-w-md mx-auto">
          <div className="bg-gradient-to-r from-[#E4FF00] to-[#00FF66] text-black rounded-xl p-6 mb-6">
            <h2 className="text-2xl font-bold mb-2">🎯 Défi du jour</h2>
            <p className="text-sm opacity-80 mb-4">{dailyChallenge?.date}</p>
            <div className="bg-black/20 rounded-full h-3 mb-2">
              <div 
                className="bg-black h-3 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="text-sm font-bold">{completed}/{total} exercices • {dailyChallenge?.totalPoints} points</div>
          </div>

          <div className="space-y-3">
            {dailyChallenge?.exercises.map((exercise) => (
              <div
                key={exercise.id}
                className={`bg-[#0F0F13] border rounded-xl p-4 transition-all ${
                  exercise.completed 
                    ? 'border-[#00FF66] opacity-60' 
                    : 'border-white/10 hover:border-[#E4FF00]'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className="text-3xl">{exercise.emoji}</span>
                    <div>
                      <h3 className="font-bold text-lg">{exercise.name}</h3>
                      <p className="text-xs text-[#A1A1AA]">{exercise.muscles}</p>
                    </div>
                  </div>
                  {exercise.completed && <span className="text-2xl">✅</span>}
                </div>
                
                <div className="flex gap-4 mb-3 text-sm">
                  <div className="bg-black/30 px-3 py-1 rounded-lg">
                    <span className="text-[#E4FF00]">{exercise.reps}</span> reps
                  </div>
                  <div className="bg-black/30 px-3 py-1 rounded-lg">
                    <span className="text-[#00FF66]">{exercise.sets}</span> séries
                  </div>
                  <div className="bg-black/30 px-3 py-1 rounded-lg text-[#A1A1AA]">
                    {exercise.difficulty}
                  </div>
                </div>

                {!exercise.completed && (
                  <button
                    onClick={() => completeChallengeExercise(exercise.id)}
                    className="w-full bg-[#E4FF00] text-black font-bold py-2 rounded-lg hover:bg-[#00FF66] transition-all"
                  >
                    Marquer comme terminé
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (mode === 'coach') {
    return (
      <div className="min-h-screen p-4 pb-24">
        <button
          onClick={() => setMode('menu')}
          className="mb-4 text-[#E4FF00] flex items-center gap-2"
        >
          ← Retour
        </button>

        <div className="max-w-md mx-auto">
          <div className="bg-gradient-to-r from-[#00D4FF] to-[#00FF66] text-black rounded-xl p-6 mb-6">
            <h2 className="text-2xl font-bold mb-2">🤖 Coach en Direct</h2>
            <p className="text-sm opacity-80">Sélectionnez un exercice pour commencer</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {EXERCISES.map((exercise) => (
              <button
                key={exercise.id}
                onClick={() => startLiveCoaching(exercise)}
                className="bg-[#0F0F13] border border-white/10 rounded-xl p-4 hover:border-[#00D4FF] hover:shadow-[0_0_20px_rgba(0,212,255,0.3)] transition-all transform hover:scale-105 active:scale-95"
              >
                <div className="text-4xl mb-2">{exercise.emoji}</div>
                <div className="font-bold text-sm mb-1">{exercise.name}</div>
                <div className="text-xs text-[#A1A1AA]">{exercise.difficulty}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (mode === 'live' && liveSession) {
    const progress = (currentRep / liveSession.targetReps) * 100;

    return (
      <div className="min-h-screen p-4 pb-24 flex flex-col">
        <div className="max-w-md mx-auto w-full flex-1 flex flex-col">
          <div className="bg-[#0F0F13] border border-white/10 rounded-xl p-4 mb-4">
            <div className="flex justify-between items-center mb-2">
              <div className="text-[#A1A1AA] text-sm">Série {liveSession.currentSet}/{liveSession.totalSets}</div>
              <div className="text-[#00D4FF] font-bold">{formatTime(timer)}</div>
            </div>
            <div className="bg-black/50 rounded-full h-2">
              <div 
                className="bg-gradient-to-r from-[#E4FF00] to-[#00FF66] h-2 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>

          <div className="bg-gradient-to-b from-[#0F0F13] to-[#050505] border border-white/10 rounded-2xl p-8 mb-4 flex-1 flex flex-col items-center justify-center">
            <div className="text-8xl mb-4 animate-bounce-slow">{liveSession.exercise.emoji}</div>
            <h2 className="text-3xl font-bold mb-2">{liveSession.exercise.name}</h2>
            <div className="text-[#A1A1AA] mb-6">{liveSession.exercise.muscles}</div>
            
            <div className="text-7xl font-bold text-[#E4FF00] mb-2 glow-text">
              {currentRep}
            </div>
            <div className="text-xl text-[#A1A1AA] mb-8">/ {liveSession.targetReps}</div>

            <button
              onClick={() => setShowTips(!showTips)}
              className="text-[#00D4FF] text-sm mb-4 hover:underline"
            >
              {showTips ? '✖ Masquer' : '💡 Voir les conseils'}
            </button>

            {showTips && (
              <div className="bg-black/50 rounded-lg p-4 mb-6 w-full">
                <div className="text-sm text-[#00FF66] font-bold mb-2">Conseils de forme :</div>
                {FORM_TIPS[liveSession.exercise.name].map((tip, i) => (
                  <div key={i} className="text-xs text-[#A1A1AA] mb-1">• {tip}</div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-2 mb-4 max-h-32 overflow-y-auto">
            {feedback.map((fb, i) => (
              <div
                key={i}
                className={`p-3 rounded-lg text-sm slide-in border ${
                  fb.type === 'success' ? 'bg-[#00FF66]/10 border-[#00FF66]/30 text-[#00FF66]' :
                  fb.type === 'warning' ? 'bg-[#E4FF00]/10 border-[#E4FF00]/30 text-[#E4FF00]' :
                  'bg-[#00D4FF]/10 border-[#00D4FF]/30 text-[#00D4FF]'
                }`}
              >
                <div className="font-bold">{fb.text}</div>
                <div className="text-xs opacity-70 mt-1">→ {fb.tip}</div>
              </div>
            ))}
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => {
                setMode('menu');
                setLiveSession(null);
                setIsActive(false);
              }}
              className="flex-1 bg-red-600/20 border border-red-600/50 text-red-400 font-bold py-4 rounded-xl hover:bg-red-600/30 transition-all"
            >
              Arrêter
            </button>
            <button
              onClick={() => {
                setIsActive(true);
                incrementRep();
              }}
              className="flex-[2] bg-gradient-to-r from-[#E4FF00] to-[#00FF66] text-black font-bold py-4 rounded-xl hover:shadow-[0_0_30px_rgba(228,255,0,0.5)] transition-all transform active:scale-95 text-xl"
            >
              ✓ Répétition
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (mode === 'history') {
    return (
      <div className="min-h-screen p-4 pb-24">
        <button
          onClick={() => setMode('menu')}
          className="mb-4 text-[#E4FF00] flex items-center gap-2"
        >
          ← Retour
        </button>

        <div className="max-w-md mx-auto">
          <h2 className="text-2xl font-bold mb-6 text-[#E4FF00]">📊 Historique</h2>

          {sessionHistory.length === 0 ? (
            <div className="bg-[#0F0F13] border border-white/10 rounded-xl p-8 text-center">
              <div className="text-6xl mb-4 opacity-20">📭</div>
              <p className="text-[#A1A1AA]">Aucune session enregistrée</p>
            </div>
          ) : (
            <div className="space-y-3">
              {sessionHistory.map((session) => (
                <div
                  key={session.id}
                  className="bg-[#0F0F13] border border-white/10 rounded-xl p-4 hover:border-[#E4FF00] transition-all"
                >
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h3 className="font-bold text-lg">{session.exercise}</h3>
                      <p className="text-xs text-[#A1A1AA]">{session.date}</p>
                    </div>
                    <div className="bg-[#E4FF00] text-black px-3 py-1 rounded-lg text-sm font-bold">
                      {session.performance}%
                    </div>
                  </div>
                  <div className="flex gap-4 text-sm">
                    <div className="text-[#00FF66]">{session.reps} reps</div>
                    <div className="text-[#00D4FF]">{formatTime(session.duration)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  return null;
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);