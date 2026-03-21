import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import axios from 'axios';
import { Phone, ArrowRight, Loader2, ArrowLeft, Wifi, WifiOff } from 'lucide-react';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function SMSLogin() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [step, setStep] = useState('phone'); // 'phone' or 'code'
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sentCode, setSentCode] = useState(null); // Pour le mode démo

  const sendCode = async () => {
    if (!phone.trim() || phone.length < 8) {
      toast.error('Numéro de téléphone invalide');
      return;
    }

    setIsLoading(true);

    try {
      const response = await axios.post(`${API}/auth/sms/send`, {
        phone_number: phone
      });

      // En mode démo, le code est retourné
      if (response.data.code) {
        setSentCode(response.data.code);
        toast.success(`Code envoyé ! (Démo: ${response.data.code})`);
      } else {
        toast.success('Code SMS envoyé !');
      }

      setStep('code');
    } catch (error) {
      console.error('SMS error:', error);
      toast.error('Erreur lors de l\'envoi du code');
    } finally {
      setIsLoading(false);
    }
  };

  const verifyCode = async () => {
    if (!code.trim() || code.length !== 6) {
      toast.error('Code à 6 chiffres requis');
      return;
    }

    setIsLoading(true);

    try {
      const response = await axios.post(
        `${API}/auth/sms/verify`,
        { phone_number: phone, code },
        { withCredentials: true }
      );

      // Update auth context
      setUser(response.data);
      toast.success('Connexion réussie !');
      navigate('/dashboard');
    } catch (error) {
      console.error('Verify error:', error);
      toast.error('Code invalide ou expiré');
    } finally {
      setIsLoading(false);
    }
  };

  const isOnline = navigator.onLine;

  return (
    <div className="min-h-screen bg-[#050505] text-white flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md"
      >
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-[#0F0F13] rounded-full border border-white/10 mb-6">
            {isOnline ? (
              <><Wifi className="w-4 h-4 text-[#00FF66]" /> <span className="text-sm">En ligne</span></>
            ) : (
              <><WifiOff className="w-4 h-4 text-orange-400" /> <span className="text-sm">Hors ligne</span></>
            )}
          </div>
          
          <h1 className="text-4xl font-['Chivo'] font-black mb-4">
            Connexion <span className="text-cyan-400">SMS</span>
          </h1>
          <p className="text-[#A1A1AA]">
            Authentification par numéro de téléphone
          </p>
        </div>

        {/* Form */}
        <div className="bg-[#0F0F13] border border-white/10 rounded-lg p-8">
          {step === 'phone' ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-6"
            >
              <div>
                <label className="block text-sm font-medium mb-2">Numéro de téléphone</label>
                <div className="relative">
                  <Phone className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-[#A1A1AA]" />
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+33 6 12 34 56 78"
                    className="w-full pl-12 pr-4 py-4 bg-[#050505] border border-white/20 rounded-lg focus:outline-none focus:border-cyan-400 text-lg"
                    data-testid="sms-phone-input"
                  />
                </div>
              </div>

              <Button
                onClick={sendCode}
                disabled={isLoading || !phone.trim()}
                className="w-full py-6 bg-cyan-400 text-[#050505] hover:bg-cyan-300 text-lg font-bold"
                data-testid="sms-send-btn"
              >
                {isLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    Envoyer le code
                    <ArrowRight className="w-5 h-5 ml-2" />
                  </>
                )}
              </Button>
            </motion.div>
          ) : (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-6"
            >
              <button
                onClick={() => setStep('phone')}
                className="flex items-center gap-2 text-[#A1A1AA] hover:text-white transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Modifier le numéro
              </button>

              <div>
                <label className="block text-sm font-medium mb-2">Code de vérification</label>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000"
                  maxLength={6}
                  className="w-full px-4 py-4 bg-[#050505] border border-white/20 rounded-lg focus:outline-none focus:border-cyan-400 text-3xl text-center tracking-[0.5em] font-mono"
                  data-testid="sms-code-input"
                />
                <p className="text-sm text-[#A1A1AA] mt-2 text-center">
                  Envoyé à {phone}
                </p>
                {sentCode && (
                  <p className="text-sm text-cyan-400 mt-1 text-center">
                    (Mode démo - Code: {sentCode})
                  </p>
                )}
              </div>

              <Button
                onClick={verifyCode}
                disabled={isLoading || code.length !== 6}
                className="w-full py-6 bg-cyan-400 text-[#050505] hover:bg-cyan-300 text-lg font-bold"
                data-testid="sms-verify-btn"
              >
                {isLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    Vérifier et se connecter
                    <ArrowRight className="w-5 h-5 ml-2" />
                  </>
                )}
              </Button>
            </motion.div>
          )}
        </div>

        {/* Back to regular login */}
        <div className="mt-6 text-center">
          <Button
            onClick={() => navigate('/login')}
            variant="ghost"
            className="text-[#A1A1AA] hover:text-white"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Retour à la connexion Google
          </Button>
        </div>

        {/* Info */}
        <div className="mt-8 text-center text-sm text-[#A1A1AA]">
          <p>💡 L'authentification SMS fonctionne même hors ligne</p>
          <p className="mt-1">après la première vérification</p>
        </div>
      </motion.div>
    </div>
  );
}
