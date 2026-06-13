const { useState, useEffect, useRef } = React;

const App = () => {
  const [mode, setMode] = useState('home');
  const [dailyChallenges, setDailyChallenges] = useState([]);
  const [completedChallenges, setCompletedChallenges] = useState([]);
  const [liveSession, setLiveSession] = useState(null);
  const [currentExercise, setCurrentExercise] = useState(0);
  const [repCount, setRepCount] = useState(0);
  const [sessionTimer, setSessionTimer] = useState(0);
  const [isSessionActive, setIsSessionActive] = useState(false);
  const [formQuality, setFormQuality] = useState([]);
  const [showFeedback, setShowFeedback] = useState(false);
  const [streak, setStreak] = useState(0);
  const [totalPoints, setTotalPoints] = useState(0);
  const [userStats, setUserStats] = useState({ workouts: 0, minutes: 0, calories: 0 });
  const videoRef = useRef(null);
  const timerRef = useRef(null);

  const exercises = [
    { name: 'Pompes', reps: 15, difficulty: 'Moyen', calories: 8, tips: ['Gardez le dos droit', 'Descendez jusqu\'à 90°', 'Respirez régulièrement'] },
    { name: 'Squats', reps: 20, difficulty: 'Facile', calories: 12, tips: ['Poussez sur les talons', 'Genoux alignés avec les pieds', 'Regard droit devant'] },
    { name: 'Planche', reps: 30, difficulty: 'Moyen', calories: 6, tips: ['Corps aligné', 'Gainage abdominal', 'Ne creusez pas le dos'] },
    { name: 'Fentes', reps: 12, difficulty: 'Moyen', calories: 10, tips: ['Genou avant à 90°', 'Gardez l\'équilibre', 'Alternez les jambes'] },
    { name: 'Burpees', reps: 10, difficulty: 'Difficile', calories: 15, tips: ['Mouvement fluide', 'Atterrissage en douceur', 'Explosivité sur le saut'] },
    { name: 'Mountain Climbers', reps: 20, difficulty: 'Difficile', calories: 14, tips: ['Rythme soutenu', 'Hanches basses', 'Gainage constant'] },
    { name: 'Jumping Jacks', reps: 25, difficulty: 'Facile', calories: 8, tips: ['Coordination bras-jambes', 'Rythme régulier', 'Atterrissage souple'] },
    { name: 'Dips', reps: 12, difficulty: 'Moyen', calories: 9, tips: ['Coudes vers l\'arrière', 'Descente contrôlée', 'Ne verrouillez pas les coudes'] }
  ];

  useEffect(() => {
    loadData();
    generateDailyChallenges();
  }, []);

  useEffect(() => {
    if (isSessionActive) {
      timerRef.current = setInterval(() => {
        setSessionTimer(prev => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isSessionActive]);

  const loadData = () => {
    const saved = localStorage.getItem('fitcoach_data');
    if (saved) {
      const data = JSON.parse(saved);
      setCompletedChallenges(data.completed || []);
      setStreak(data.streak || 0);
      setTotalPoints(data.points || 0);
      setUserStats(data.stats || { workouts: 0, minutes: 0, calories: 0 });
    }
  };

  const saveData = (data) => {
    localStorage.setItem('fitcoach_data', JSON.stringify(data));
  };

  const generateDailyChallenges = () => {
    const today = new Date().toDateString();
    const saved = localStorage.getItem('daily_challenges_date');
    
    if (saved === today) {
      const challenges = JSON.parse(localStorage.getItem('daily_challenges'));
      setDailyChallenges(challenges);
      return;
    }

    const shuffled = [...exercises].sort(() => Math.random() - 0.5);
    const challenges = shuffled.slice(0, 4).map((ex, idx) => ({
      id: Date.now() + idx,
      ...ex,
      sets: Math.floor(Math.random() * 2) + 2,
      bonus: Math.floor(Math.random() * 50) + 50
    }));

    setDailyChallenges(challenges);
    localStorage.setItem('daily_challenges', JSON.stringify(challenges));
    localStorage.setItem('daily_challenges_date', today);
  };

  const startLiveSession = () => {
    const sessionExercises = [...exercises].sort(() => Math.random() - 0.5).slice(0, 5);
    setLiveSession(sessionExercises);
    setCurrentExercise(0);
    setRepCount(0);
    setSessionTimer(0);
    setFormQuality([]);
    setIsSessionActive(true);
    setMode('live');
    requestCameraAccess();
  };

  const requestCameraAccess = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      console.log('Caméra non disponible, mode simulation activé');
    }
  };

  const simulateRepDetection = () => {
    if (!isSessionActive || !liveSession) return;

    const quality = Math.random() > 0.3 ? 'good' : Math.random() > 0.5 ? 'perfect' : 'needs-work';
    const newCount = repCount + 1;
    setRepCount(newCount);
    setFormQuality(prev => [...prev, quality]);

    if (quality === 'needs-work') {
      setShowFeedback(true);
      setTimeout(() => setShowFeedback(false), 2000);
    }

    if (newCount >= liveSession[currentExercise].reps) {
      setTimeout(() => nextExercise(), 1500);
    }
  };

  const nextExercise = () => {
    if (currentExercise < liveSession.length - 1) {
      setCurrentExercise(prev => prev + 1);
      setRepCount(0);
      setFormQuality([]);
    } else {
      endSession();
    }
  };

  const endSession = () => {
    setIsSessionActive(false);
    const minutes = Math.floor(sessionTimer / 60);
    const totalCalories = liveSession.reduce((sum, ex) => sum + ex.calories, 0);
    const points = Math.floor(formQuality.filter(q => q === 'perfect').length * 10 + formQuality.filter(q => q === 'good').length * 5);

    const newStats = {
      workouts: userStats.workouts + 1,
      minutes: userStats.minutes + minutes,
      calories: userStats.calories + totalCalories
    };

    const newPoints = totalPoints + points;
    
    setUserStats(newStats);
    setTotalPoints(newPoints);
    
    saveData({
      completed: completedChallenges,
      streak: streak,
      points: newPoints,
      stats: newStats
    });

    if (videoRef.current && videoRef.current.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(track => track.stop());
    }

    setTimeout(() => setMode('sessionComplete'), 500);
  };

  const completeChallenge = (challengeId) => {
    const challenge = dailyChallenges.find(c => c.id === challengeId);
    if (!challenge) return;

    const newCompleted = [...completedChallenges, challengeId];
    const newPoints = totalPoints + challenge.bonus;
    const newStreak = streak + 1;

    setCompletedChallenges(newCompleted);
    setTotalPoints(newPoints);
    setStreak(newStreak);

    saveData({
      completed: newCompleted,
      streak: newStreak,
      points: newPoints,
      stats: userStats
    });
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const HomePage = () => (
    <div className="min-h-screen p-4 pb-24">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8 text-center">
          <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-[#E4FF00] to-[#00FF66] bg-clip-text text-transparent">FitCoach Pro</h1>
          <p className="text-[#A1A1AA]">Ton coach personnel intelligent</p>
        </header>

        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-[#0F0F13] rounded-xl p-4 border border-white/10">
            <div className="text-[#00FF66] text-3xl font-bold">{streak}</div>
            <div className="text-sm text-[#A1A1AA]">Série</div>
          </div>
          <div className="bg-[#0F0F13] rounded-xl p-4 border border-white/10">
            <div className="text-[#E4FF00] text-3xl font-bold">{totalPoints}</div>
            <div className="text-sm text-[#A1A1AA]">Points</div>
          </div>
          <div className="bg-[#0F0F13] rounded-xl p-4 border border-white/10">
            <div className="text-[#00D4FF] text-3xl font-bold">{userStats.workouts}</div>
            <div className="text-sm text-[#A1A1AA]">Séances</div>
          </div>
        </div>

        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold">Défis du Jour</h2>
            <div className="text-sm text-[#A1A1AA]">{completedChallenges.length}/{dailyChallenges.length} complétés</div>
          </div>
          <div className="grid gap-4">
            {dailyChallenges.map(challenge => {
              const isCompleted = completedChallenges.includes(challenge.id);
              return (
                <div key={challenge.id} className={`bg-[#0F0F13] rounded-xl p-4 border transition-all ${
                  isCompleted ? 'border-[#00FF66]/50 opacity-60' : 'border-white/10 hover:border-[#E4FF00]/50'
                }`}>
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="font-bold text-lg">{challenge.name}</h3>
                      <p className="text-sm text-[#A1A1AA]">{challenge.sets} séries × {challenge.reps} reps</p>
                    </div>
                    <div className="text-right">
                      <div className="text-[#E4FF00] font-bold">+{challenge.bonus}</div>
                      <div className="text-xs text-[#A1A1AA]">points</div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className={`px-3 py-1 rounded-full text-xs ${
                      challenge.difficulty === 'Facile' ? 'bg-[#00FF66]/20 text-[#00FF66]' :
                      challenge.difficulty === 'Moyen' ? 'bg-[#E4FF00]/20 text-[#E4FF00]' :
                      'bg-[#FF006E]/20 text-[#FF006E]'
                    }`}>{challenge.difficulty}</span>
                    <button
                      onClick={() => completeChallenge(challenge.id)}
                      disabled={isCompleted}
                      className={`px-4 py-2 rounded-lg font-semibold transition-all ${
                        isCompleted
                          ? 'bg-[#00FF66]/20 text-[#00FF66] cursor-not-allowed'
                          : 'bg-[#E4FF00] text-black hover:shadow-[0_0_20px_rgba(228,255,0,0.5)]'
                      }`}
                    >
                      {isCompleted ? '✓ Terminé' : 'Valider'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <button
          onClick={startLiveSession}
          className="w-full bg-gradient-to-r from-[#E4FF00] to-[#00FF66] text-black font-bold py-6 rounded-xl text-lg shadow-[0_0_30px_rgba(228,255,0,0.3)] hover:shadow-[0_0_40px_rgba(228,255,0,0.5)] transition-all pulse-animation"
        >
          🎯 Démarrer Session Coaching Live
        </button>

        <div className="mt-8 grid grid-cols-3 gap-4">
          <div className="bg-[#0F0F13] rounded-xl p-4 border border-white/10 text-center">
            <div className="text-2xl mb-1">⏱️</div>
            <div className="text-lg font-bold text-[#E4FF00]">{userStats.minutes}</div>
            <div className="text-xs text-[#A1A1AA]">Minutes</div>
          </div>
          <div className="bg-[#0F0F13] rounded-xl p-4 border border-white/10 text-center">
            <div className="text-2xl mb-1">🔥</div>
            <div className="text-lg font-bold text-[#FF006E]">{userStats.calories}</div>
            <div className="text-xs text-[#A1A1AA]">Calories</div>
          </div>
          <div className="bg-[#0F0F13] rounded-xl p-4 border border-white/10 text-center">
            <div className="text-2xl mb-1">💪</div>
            <div className="text-lg font-bold text-[#00D4FF]">{exercises.length}</div>
            <div className="text-xs text-[#A1A1AA]">Exercices</div>
          </div>
        </div>
      </div>
    </div>
  );

  const LiveSessionView = () => {
    if (!liveSession) return null;
    const exercise = liveSession[currentExercise];
    const progress = (repCount / exercise.reps) * 100;
    const goodReps = formQuality.filter(q => q === 'good' || q === 'perfect').length;
    const accuracy = formQuality.length > 0 ? Math.round((goodReps / formQuality.length) * 100) : 0;

    return (
      <div className="min-h-screen p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-4">
            <div className="text-sm text-[#A1A1AA]">Exercice {currentExercise + 1}/{liveSession.length}</div>
            <div className="text-lg font-bold text-[#00D4FF]">{formatTime(sessionTimer)}</div>
          </div>

          <div className="bg-[#0F0F13] rounded-xl overflow-hidden mb-4 relative" style={{height: '300px'}}>
            <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 to-transparent" />
            <div className="absolute bottom-4 left-4 right-4">
              <h2 className="text-3xl font-bold mb-2">{exercise.name}</h2>
              <div className="flex items-center gap-4">
                <div className="text-[#E4FF00] text-5xl font-bold">{repCount}/{exercise.reps}</div>
                <div className="flex-1">
                  <div className="bg-white/10 rounded-full h-3 overflow-hidden">
                    <div className="bg-gradient-to-r from-[#E4FF00] to-[#00FF66] h-full transition-all duration-300" style={{width: `${progress}%`}} />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-[#0F0F13] rounded-xl p-4 border border-white/10 mb-4">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-semibold">Qualité d'exécution</div>
              <div className="text-[#00FF66] font-bold">{accuracy}%</div>
            </div>
            <div className="flex gap-1">
              {Array.from({ length: exercise.reps }).map((_, idx) => (
                <div key={idx} className={`flex-1 h-2 rounded-full ${
                  idx < formQuality.length
                    ? formQuality[idx] === 'perfect' ? 'bg-[#00FF66]'
                    : formQuality[idx] === 'good' ? 'bg-[#E4FF00]'
                    : 'bg-[#FF006E]'
                    : 'bg-white/10'
                }`} />
              ))}
            </div>
          </div>

          {showFeedback && (
            <div className="bg-[#FF006E]/20 border border-[#FF006E]/50 rounded-xl p-4 mb-4 animate-pulse">
              <div className="font-bold text-[#FF006E] mb-2">⚠️ Ajuste ta position</div>
              <ul className="text-sm space-y-1">
                {exercise.tips.slice(0, 2).map((tip, idx) => (
                  <li key={idx} className="text-[#A1A1AA]">• {tip}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="bg-[#0F0F13] rounded-xl p-4 border border-white/10 mb-4">
            <div className="font-semibold mb-2">💡 Conseils du Coach</div>
            <ul className="space-y-2">
              {exercise.tips.map((tip, idx) => (
                <li key={idx} className="text-sm text-[#A1A1AA] flex items-start gap-2">
                  <span className="text-[#00FF66]">✓</span>
                  <span>{tip}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <button
              onClick={simulateRepDetection}
              disabled={!isSessionActive}
              className="bg-gradient-to-r from-[#E4FF00] to-[#00FF66] text-black font-bold py-4 rounded-xl text-lg shadow-[0_0_20px_rgba(228,255,0,0.3)] hover:shadow-[0_0_30px_rgba(228,255,0,0.5)] transition-all disabled:opacity-50"
            >
              ✓ Compter Rep
            </button>
            <button
              onClick={endSession}
              className="bg-[#FF006E]/20 border border-[#FF006E]/50 text-[#FF006E] font-bold py-4 rounded-xl hover:bg-[#FF006E]/30 transition-all"
            >
              ⏸️ Terminer
            </button>
          </div>
        </div>
      </div>
    );
  };

  const SessionCompleteView = () => {
    const minutes = Math.floor(sessionTimer / 60);
    const totalCalories = liveSession?.reduce((sum, ex) => sum + ex.calories, 0) || 0;
    const perfectReps = formQuality.filter(q => q === 'perfect').length;
    const goodReps = formQuality.filter(q => q === 'good').length;
    const accuracy = formQuality.length > 0 ? Math.round(((perfectReps + goodReps) / formQuality.length) * 100) : 0;

    return (
      <div className="min-h-screen p-4 flex items-center justify-center">
        <div className="max-w-md w-full">
          <div className="text-center mb-8">
            <div className="text-6xl mb-4">🏆</div>
            <h2 className="text-3xl font-bold mb-2">Excellent Travail !</h2>
            <p className="text-[#A1A1AA]">Session terminée avec succès</p>
          </div>

          <div className="bg-[#0F0F13] rounded-xl p-6 border border-white/10 mb-6">
            <div className="grid grid-cols-2 gap-6">
              <div className="text-center">
                <div className="text-[#E4FF00] text-3xl font-bold">{minutes}</div>
                <div className="text-sm text-[#A1A1AA]">Minutes</div>
              </div>
              <div className="text-center">
                <div className="text-[#FF006E] text-3xl font-bold">{totalCalories}</div>
                <div className="text-sm text-[#A1A1AA]">Calories</div>
              </div>
              <div className="text-center">
                <div className="text-[#00FF66] text-3xl font-bold">{accuracy}%</div>
                <div className="text-sm text-[#A1A1AA]">Précision</div>
              </div>
              <div className="text-center">
                <div className="text-[#00D4FF] text-3xl font-bold">{liveSession?.length || 0}</div>
                <div className="text-sm text-[#A1A1AA]">Exercices</div>
              </div>
            </div>
          </div>

          <div className="bg-[#0F0F13] rounded-xl p-6 border border-white/10 mb-6">
            <div className="font-semibold mb-3">📊 Analyse de Performance</div>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-[#A1A1AA]">Reps parfaites</span>
                <span className="text-[#00FF66] font-bold">{perfectReps}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-[#A1A1AA]">Reps correctes</span>
                <span className="text-[#E4FF00] font-bold">{goodReps}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-[#A1A1AA]">Points gagnés</span>
                <span className="text-[#00D4FF] font-bold">+{perfectReps * 10 + goodReps * 5}</span>
              </div>
            </div>
          </div>

          <button
            onClick={() => setMode('home')}
            className="w-full bg-gradient-to-r from-[#E4FF00] to-[#00FF66] text-black font-bold py-4 rounded-xl text-lg shadow-[0_0_30px_rgba(228,255,0,0.3)] hover:shadow-[0_0_40px_rgba(228,255,0,0.5)] transition-all"
          >
            Retour à l'Accueil
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="app-container">
      {mode === 'home' && <HomePage />}
      {mode === 'live' && <LiveSessionView />}
      {mode === 'sessionComplete' && <SessionCompleteView />}
    </div>
  );
};

ReactDOM.render(<App />, document.getElementById('root'));