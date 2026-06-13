const { useState, useEffect, useRef } = React;

const DANCE_STYLES = [
  { id: 'hip-hop', name: 'Hip-Hop', icon: '🎤', color: '#E4FF00' },
  { id: 'salsa', name: 'Salsa', icon: '💃', color: '#00FF66' },
  { id: 'breakdance', name: 'Breakdance', icon: '🕺', color: '#00D4FF' },
  { id: 'contemporain', name: 'Contemporain', icon: '🩰', color: '#FF006E' }
];

const DAILY_CHALLENGES = [
  {
    id: 1,
    title: 'Isolation des épaules',
    style: 'hip-hop',
    duration: 5,
    difficulty: 'Débutant',
    points: 100,
    steps: [
      'Échauffement : 30 secondes de rotation des épaules',
      'Isolation droite : montez uniquement l\'épaule droite (10 fois)',
      'Isolation gauche : montez uniquement l\'épaule gauche (10 fois)',
      'Alternance rapide : droite-gauche pendant 20 secondes',
      'Mouvement fluide : créez une vague avec les deux épaules'
    ],
    corrections: [
      'Gardez le buste immobile',
      'Isolez uniquement les épaules',
      'Respirez naturellement',
      'Maintenez le rythme constant'
    ]
  },
  {
    id: 2,
    title: 'Pas de base Salsa',
    style: 'salsa',
    duration: 8,
    difficulty: 'Débutant',
    points: 150,
    steps: [
      'Position de base : pieds écartés largeur des hanches',
      'Temps 1 : pas gauche en avant',
      'Temps 2 : transfert de poids sur place',
      'Temps 3 : pied gauche revient',
      'Répétez en arrière avec le pied droit',
      'Ajoutez les hanches : balancez naturellement'
    ],
    corrections: [
      'Pliez légèrement les genoux',
      'Le mouvement vient des hanches',
      'Gardez le haut du corps stable',
      'Comptez : 1-2-3, 5-6-7'
    ]
  },
  {
    id: 3,
    title: 'Freeze Basique',
    style: 'breakdance',
    duration: 10,
    difficulty: 'Intermédiaire',
    points: 200,
    steps: [
      'Positionnez-vous à quatre pattes',
      'Placez la main droite au sol, coude plié',
      'Posez le coude droit sur le ventre',
      'Transférez le poids sur le bras droit',
      'Levez les jambes en équilibre',
      'Maintenez 5 secondes minimum'
    ],
    corrections: [
      'Contractez les abdominaux',
      'Le coude doit être bien calé',
      'Regardez le sol pour l\'équilibre',
      'Progressez lentement, sécurité avant tout'
    ]
  },
  {
    id: 4,
    title: 'Contraction-Release',
    style: 'contemporain',
    duration: 7,
    difficulty: 'Intermédiaire',
    points: 180,
    steps: [
      'Debout, bras le long du corps',
      'Inspiration : contractez tout le corps',
      'Expiration : relâchez complètement',
      'Répétez en ajoutant les bras',
      'Intégrez le mouvement au sol',
      'Créez votre propre séquence'
    ],
    corrections: [
      'Synchronisez avec la respiration',
      'Contraste fort/doux doit être visible',
      'Utilisez tout l\'espace',
      'Soyez expressif avec le visage'
    ]
  }
];

function App() {
  const [currentView, setCurrentView] = useState('home');
  const [selectedChallenge, setSelectedChallenge] = useState(null);
  const [challengeProgress, setChallengeProgress] = useState(0);
  const [completedChallenges, setCompletedChallenges] = useState([]);
  const [totalPoints, setTotalPoints] = useState(0);
  const [isCoaching, setIsCoaching] = useState(false);
  const [coachingStep, setCoachingStep] = useState(0);
  const [coachingTimer, setCoachingTimer] = useState(0);
  const [currentCorrection, setCurrentCorrection] = useState('');
  const [userStats, setUserStats] = useState({
    streak: 0,
    totalSessions: 0,
    favoriteStyle: 'hip-hop'
  });
  const timerRef = useRef(null);

  useEffect(() => {
    const savedData = localStorage.getItem('danceflow_data');
    if (savedData) {
      const data = JSON.parse(savedData);
      setCompletedChallenges(data.completed || []);
      setTotalPoints(data.points || 0);
      setUserStats(data.stats || userStats);
    }

    const lastVisit = localStorage.getItem('danceflow_last_visit');
    const today = new Date().toDateString();
    if (lastVisit !== today) {
      localStorage.setItem('danceflow_last_visit', today);
      if (lastVisit) {
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        if (lastVisit === yesterday.toDateString()) {
          setUserStats(prev => ({ ...prev, streak: prev.streak + 1 }));
        } else {
          setUserStats(prev => ({ ...prev, streak: 1 }));
        }
      }
    }
  }, []);

  useEffect(() => {
    const dataToSave = {
      completed: completedChallenges,
      points: totalPoints,
      stats: userStats
    };
    localStorage.setItem('danceflow_data', JSON.stringify(dataToSave));
  }, [completedChallenges, totalPoints, userStats]);

  useEffect(() => {
    if (isCoaching && coachingTimer > 0) {
      timerRef.current = setTimeout(() => {
        setCoachingTimer(coachingTimer - 1);
      }, 1000);
    } else if (isCoaching && coachingTimer === 0 && selectedChallenge) {
      if (coachingStep < selectedChallenge.steps.length - 1) {
        setTimeout(() => {
          setCoachingStep(coachingStep + 1);
          setCoachingTimer(15);
          showRandomCorrection();
        }, 1000);
      } else {
        completeChallenge();
      }
    }
    return () => clearTimeout(timerRef.current);
  }, [isCoaching, coachingTimer, coachingStep]);

  const showRandomCorrection = () => {
    if (selectedChallenge && Math.random() > 0.5) {
      const corrections = selectedChallenge.corrections;
      const randomCorrection = corrections[Math.floor(Math.random() * corrections.length)];
      setCurrentCorrection(randomCorrection);
      setTimeout(() => setCurrentCorrection(''), 3000);
    }
  };

  const startChallenge = (challenge) => {
    setSelectedChallenge(challenge);
    setChallengeProgress(0);
    setCurrentView('challenge');
  };

  const startCoaching = () => {
    setIsCoaching(true);
    setCoachingStep(0);
    setCoachingTimer(15);
    showRandomCorrection();
  };

  const completeChallenge = () => {
    if (!completedChallenges.includes(selectedChallenge.id)) {
      setCompletedChallenges([...completedChallenges, selectedChallenge.id]);
      setTotalPoints(totalPoints + selectedChallenge.points);
      setUserStats(prev => ({
        ...prev,
        totalSessions: prev.totalSessions + 1
      }));
    }
    setIsCoaching(false);
    setChallengeProgress(100);
  };

  const resetChallenge = () => {
    setIsCoaching(false);
    setCoachingStep(0);
    setCoachingTimer(0);
    setChallengeProgress(0);
    setCurrentCorrection('');
  };

  const getTodayChallenge = () => {
    const dayOfYear = Math.floor((new Date() - new Date(new Date().getFullYear(), 0, 0)) / 86400000);
    return DAILY_CHALLENGES[dayOfYear % DAILY_CHALLENGES.length];
  };

  const getAvailableChallenges = () => {
    return DAILY_CHALLENGES.filter(c => c.id !== getTodayChallenge().id);
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const renderHome = () => (
    <div className="min-h-screen p-4 pb-24">
      <header className="mb-8 animate-fade-in">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-[#E4FF00] to-[#00FF66] bg-clip-text text-transparent">
              DanceFlow
            </h1>
            <p className="text-[#A1A1AA] mt-1">Ton coach de danse personnel</p>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-[#E4FF00]">{totalPoints}</div>
            <div className="text-sm text-[#A1A1AA]">points</div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="bg-[#0F0F13] p-4 rounded-xl border border-white/10">
            <div className="text-2xl mb-1">🔥</div>
            <div className="text-xl font-bold text-[#00FF66]">{userStats.streak}</div>
            <div className="text-xs text-[#A1A1AA]">jours</div>
          </div>
          <div className="bg-[#0F0F13] p-4 rounded-xl border border-white/10">
            <div className="text-2xl mb-1">💪</div>
            <div className="text-xl font-bold text-[#00D4FF]">{userStats.totalSessions}</div>
            <div className="text-xs text-[#A1A1AA]">sessions</div>
          </div>
          <div className="bg-[#0F0F13] p-4 rounded-xl border border-white/10">
            <div className="text-2xl mb-1">⭐</div>
            <div className="text-xl font-bold text-[#E4FF00]">{completedChallenges.length}</div>
            <div className="text-xs text-[#A1A1AA]">défis</div>
          </div>
        </div>
      </header>

      <section className="mb-8 animate-slide-up" style={{animationDelay: '0.1s'}}>
        <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
          <span className="text-3xl">🎯</span>
          Défi du jour
        </h2>
        {(() => {
          const todayChallenge = getTodayChallenge();
          const isCompleted = completedChallenges.includes(todayChallenge.id);
          const style = DANCE_STYLES.find(s => s.id === todayChallenge.style);
          return (
            <div 
              className="bg-gradient-to-br from-[#0F0F13] to-[#1A1A1F] p-6 rounded-2xl border border-white/10 shadow-[0_0_30px_rgba(228,255,0,0.2)] cursor-pointer transform transition-all hover:scale-[1.02] active:scale-[0.98]"
              onClick={() => startChallenge(todayChallenge)}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="text-4xl">{style.icon}</div>
                  <div>
                    <h3 className="text-xl font-bold">{todayChallenge.title}</h3>
                    <p className="text-sm text-[#A1A1AA]">{style.name} • {todayChallenge.duration} min</p>
                  </div>
                </div>
                {isCompleted && (
                  <div className="bg-[#00FF66]/20 text-[#00FF66] px-3 py-1 rounded-full text-sm font-semibold">
                    ✓ Terminé
                  </div>
                )}
              </div>
              <div className="flex items-center justify-between">
                <span className="px-3 py-1 bg-[#E4FF00]/10 text-[#E4FF00] rounded-full text-sm font-semibold">
                  {todayChallenge.difficulty}
                </span>
                <span className="text-[#E4FF00] font-bold text-lg">+{todayChallenge.points} pts</span>
              </div>
            </div>
          );
        })()}
      </section>

      <section className="mb-8 animate-slide-up" style={{animationDelay: '0.2s'}}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <span className="text-3xl">🎪</span>
            Tous les défis
          </h2>
        </div>
        <div className="grid gap-4">
          {getAvailableChallenges().map((challenge, index) => {
            const isCompleted = completedChallenges.includes(challenge.id);
            const style = DANCE_STYLES.find(s => s.id === challenge.style);
            return (
              <div 
                key={challenge.id}
                className="bg-[#0F0F13] p-4 rounded-xl border border-white/10 cursor-pointer transform transition-all hover:border-[#E4FF00]/30 hover:shadow-lg active:scale-[0.98] animate-slide-up"
                style={{animationDelay: `${0.3 + index * 0.1}s`}}
                onClick={() => startChallenge(challenge)}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="text-3xl">{style.icon}</div>
                    <div>
                      <h3 className="font-bold">{challenge.title}</h3>
                      <p className="text-sm text-[#A1A1AA]">{style.name} • {challenge.duration} min</p>
                    </div>
                  </div>
                  {isCompleted && <span className="text-[#00FF66] text-xl">✓</span>}
                </div>
                <div className="flex items-center justify-between">
                  <span className="px-2 py-1 bg-white/5 rounded-full text-xs text-[#A1A1AA]">
                    {challenge.difficulty}
                  </span>
                  <span className="text-[#E4FF00] font-semibold text-sm">+{challenge.points}</span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="animate-slide-up" style={{animationDelay: '0.4s'}}>
        <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
          <span className="text-3xl">💎</span>
          Styles de danse
        </h2>
        <div className="grid grid-cols-2 gap-3">
          {DANCE_STYLES.map((style, index) => (
            <div 
              key={style.id}
              className="bg-[#0F0F13] p-4 rounded-xl border border-white/10 text-center cursor-pointer transform transition-all hover:scale-105 active:scale-95 animate-scale-in"
              style={{animationDelay: `${0.5 + index * 0.1}s`}}
            >
              <div className="text-4xl mb-2">{style.icon}</div>
              <div className="font-bold">{style.name}</div>
              <div className="text-xs text-[#A1A1AA] mt-1">
                {DAILY_CHALLENGES.filter(c => c.style === style.id).length} défis
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );

  const renderChallenge = () => {
    if (!selectedChallenge) return null;
    const style = DANCE_STYLES.find(s => s.id === selectedChallenge.style);
    const isCompleted = completedChallenges.includes(selectedChallenge.id);
    const progress = isCoaching ? ((coachingStep + 1) / selectedChallenge.steps.length) * 100 : challengeProgress;

    return (
      <div className="min-h-screen p-4 pb-24">
        <button 
          onClick={() => {
            resetChallenge();
            setCurrentView('home');
          }}
          className="mb-6 flex items-center gap-2 text-[#A1A1AA] hover:text-white transition-colors"
        >
          <span className="text-xl">←</span> Retour
        </button>

        <div className="mb-6 animate-fade-in">
          <div className="flex items-center gap-4 mb-4">
            <div className="text-5xl">{style.icon}</div>
            <div className="flex-1">
              <h1 className="text-3xl font-bold mb-1">{selectedChallenge.title}</h1>
              <p className="text-[#A1A1AA]">{style.name} • {selectedChallenge.duration} minutes</p>
            </div>
          </div>

          <div className="flex gap-3 mb-4">
            <div className="flex-1 bg-[#0F0F13] px-4 py-2 rounded-lg border border-white/10">
              <div className="text-xs text-[#A1A1AA] mb-1">Difficulté</div>
              <div className="font-semibold">{selectedChallenge.difficulty}</div>
            </div>
            <div className="flex-1 bg-[#0F0F13] px-4 py-2 rounded-lg border border-white/10">
              <div className="text-xs text-[#A1A1AA] mb-1">Points</div>
              <div className="font-semibold text-[#E4FF00]">+{selectedChallenge.points}</div>
            </div>
          </div>

          <div className="bg-[#0F0F13] rounded-full h-3 overflow-hidden border border-white/10">
            <div 
              className="h-full bg-gradient-to-r from-[#E4FF00] to-[#00FF66] transition-all duration-500 ease-out"
              style={{width: `${progress}%`}}
            />
          </div>
          <div className="text-right text-sm text-[#A1A1AA] mt-1">
            {Math.round(progress)}% complété
          </div>
        </div>

        {!isCoaching && challengeProgress === 0 && (
          <div className="animate-slide-up">
            <div className="bg-[#0F0F13] p-6 rounded-2xl border border-white/10 mb-6">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="text-2xl">📋</span>
                Étapes du défi
              </h2>
              <div className="space-y-3">
                {selectedChallenge.steps.map((step, index) => (
                  <div key={index} className="flex gap-3 items-start">
                    <div className="w-8 h-8 rounded-full bg-[#E4FF00]/10 border border-[#E4FF00] flex items-center justify-center flex-shrink-0 font-bold text-[#E4FF00]">
                      {index + 1}
                    </div>
                    <p className="text-[#E0E0E0] pt-1">{step}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-[#0F0F13] p-6 rounded-2xl border border-white/10 mb-6">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span className="text-2xl">💡</span>
                Conseils du coach
              </h2>
              <div className="space-y-2">
                {selectedChallenge.corrections.map((tip, index) => (
                  <div key={index} className="flex gap-3 items-start">
                    <span className="text-[#00FF66] text-xl flex-shrink-0">✓</span>
                    <p className="text-[#A1A1AA]">{tip}</p>
                  </div>
                ))}
              </div>
            </div>

            <button
              onClick={startCoaching}
              className="w-full bg-gradient-to-r from-[#E4FF00] to-[#00FF66] text-black font-bold py-5 rounded-xl text-lg shadow-[0_0_30px_rgba(228,255,0,0.3)] hover:shadow-[0_0_40px_rgba(228,255,0,0.5)] transform transition-all active:scale-95 pulse-button"
            >
              🎬 Démarrer le coaching en direct
            </button>
          </div>
        )}

        {isCoaching && (
          <div className="animate-fade-in">
            <div className="bg-gradient-to-br from-[#0F0F13] to-[#1A1A1F] p-8 rounded-2xl border border-[#E4FF00]/30 shadow-[0_0_40px_rgba(228,255,0,0.2)] mb-6">
              <div className="text-center mb-6">
                <div className="text-7xl font-bold text-[#E4FF00] mb-2 animate-pulse-slow">
                  {formatTime(coachingTimer)}
                </div>
                <div className="text-[#A1A1AA]">Temps restant pour cette étape</div>
              </div>

              <div className="bg-black/30 p-6 rounded-xl border border-white/10 mb-6">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-full bg-[#00FF66] flex items-center justify-center font-bold text-black text-lg">
                    {coachingStep + 1}
                  </div>
                  <h3 className="text-xl font-bold">Étape {coachingStep + 1}/{selectedChallenge.steps.length}</h3>
                </div>
                <p className="text-lg text-[#E0E0E0] leading-relaxed">
                  {selectedChallenge.steps[coachingStep]}
                </p>
              </div>

              {currentCorrection && (
                <div className="bg-gradient-to-r from-[#00D4FF]/20 to-[#00FF66]/20 border-l-4 border-[#00D4FF] p-4 rounded-lg mb-4 animate-slide-in">
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">👨‍🏫</span>
                    <div>
                      <div className="font-bold text-[#00D4FF] mb-1">Correction du coach</div>
                      <p className="text-sm text-[#E0E0E0]">{currentCorrection}</p>
                    </div>
                  </div>
                </div>
              )}

              <div className="flex gap-3">
                <button
                  onClick={() => {
                    if (coachingStep > 0) {
                      setCoachingStep(coachingStep - 1);
                      setCoachingTimer(15);
                    }
                  }}
                  disabled={coachingStep === 0}
                  className="flex-1 bg-white/5 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-lg transition-all"
                >
                  ← Précédent
                </button>
                <button
                  onClick={() => {
                    if (coachingStep < selectedChallenge.steps.length - 1) {
                      setCoachingStep(coachingStep + 1);
                      setCoachingTimer(15);
                      showRandomCorrection();
                    } else {
                      completeChallenge();
                    }
                  }}
                  className="flex-1 bg-gradient-to-r from-[#00FF66] to-[#00D4FF] text-black font-bold py-3 rounded-lg transition-all hover:shadow-lg"
                >
                  {coachingStep < selectedChallenge.steps.length - 1 ? 'Suivant →' : '✓ Terminer'}
                </button>
              </div>
            </div>

            <button
              onClick={resetChallenge}
              className="w-full bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 font-semibold py-3 rounded-lg transition-all"
            >
              Arrêter la session
            </button>
          </div>
        )}

        {challengeProgress === 100 && !isCoaching && (
          <div className="animate-scale-in">
            <div className="bg-gradient-to-br from-[#E4FF00]/10 to-[#00FF66]/10 border-2 border-[#E4FF00] p-8 rounded-2xl text-center shadow-[0_0_50px_rgba(228,255,0,0.3)] mb-6">
              <div className="text-7xl mb-4 animate-bounce-slow">🎉</div>
              <h2 className="text-3xl font-bold mb-2">Défi terminé !</h2>
              <p className="text-[#A1A1AA] mb-6">Excellent travail ! Continue comme ça !</p>
              <div className="bg-black/30 p-4 rounded-xl inline-block mb-6">
                <div className="text-5xl font-bold text-[#E4FF00]">+{selectedChallenge.points}</div>
                <div className="text-[#A1A1AA]">points gagnés</div>
              </div>
              <button
                onClick={() => {
                  resetChallenge();
                  setCurrentView('home');
                }}
                className="w-full bg-gradient-to-r from-[#E4FF00] to-[#00FF66] text-black font-bold py-4 rounded-xl text-lg shadow-lg hover:shadow-xl transform transition-all active:scale-95"
              >
                Retour à l'accueil
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-2xl mx-auto">
      {currentView === 'home' && renderHome()}
      {currentView === 'challenge' && renderChallenge()}
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);