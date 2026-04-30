import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, FileText, Shield, Cookie } from 'lucide-react';

const TABS = [
  { key: 'cgu', label: "Conditions d'utilisation", icon: FileText },
  { key: 'privacy', label: 'Confidentialité (RGPD)', icon: Shield },
  { key: 'cookies', label: 'Cookies', icon: Cookie },
];

export default function Legal() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [tab, setTab] = useState(params.get('tab') || 'cgu');

  return (
    <div className="min-h-screen bg-[#050505] relative">
      <div className="fixed inset-0 noise-bg pointer-events-none"></div>
      <div className="relative z-10 max-w-3xl mx-auto px-4 py-10">
        <button
          onClick={() => navigate(-1)}
          data-testid="legal-back-btn"
          className="inline-flex items-center gap-2 text-sm text-[#A1A1AA] hover:text-[#E4FF00] transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" /> Retour
        </button>

        <motion.h1
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          className="text-3xl sm:text-4xl font-['Chivo'] font-black text-white"
        >
          Mentions légales
        </motion.h1>
        <p className="text-sm text-[#A1A1AA] mt-1">Dernière mise à jour : 30 avril 2026</p>

        <div className="mt-6 flex flex-wrap gap-2 border-b border-white/10">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              data-testid={`legal-tab-${key}`}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-['Chivo'] font-bold border-b-2 -mb-px transition-colors ${
                tab === key ? 'text-[#E4FF00] border-[#E4FF00]' : 'text-[#A1A1AA] border-transparent hover:text-white'
              }`}
            >
              <Icon className="w-4 h-4" /> {label}
            </button>
          ))}
        </div>

        <div className="mt-6 bg-white/[0.03] border border-white/10 rounded-sm p-6 backdrop-blur-xl text-[#E4E4E7] font-['IBM_Plex_Sans'] leading-relaxed text-sm space-y-4">
          {tab === 'cgu' && <CGU />}
          {tab === 'privacy' && <Privacy />}
          {tab === 'cookies' && <Cookies />}
        </div>
      </div>
    </div>
  );
}

const H = ({ children }) => <h2 className="text-base font-['Chivo'] font-bold text-white mt-5">{children}</h2>;

const CGU = () => (
  <div data-testid="legal-cgu" className="space-y-3">
    <H>1. Objet</H>
    <p>CodeForge AI ("le Service") est une plateforme de génération assistée par IA d'applications web, mobiles (PWA) et desktop (.exe).</p>
    <H>2. Compte utilisateur</H>
    <p>L'inscription est gratuite et ouverte aux personnes majeures (18 ans et +). Tu es responsable de la confidentialité de ton mot de passe et de toute activité sur ton compte.</p>
    <H>3. Usage acceptable</H>
    <p>Tu t'engages à ne pas utiliser le Service pour : générer du code malveillant, harceler des tiers, violer des droits d'auteur, ou enfreindre toute loi applicable. Le Service peut suspendre tout compte enfreignant ces règles.</p>
    <H>4. Propriété intellectuelle</H>
    <p>Le code généré par l'IA t'appartient et tu peux l'utiliser librement, y compris commercialement. La marque "CodeForge AI" et son interface restent la propriété de leurs auteurs.</p>
    <H>5. Disponibilité</H>
    <p>Le Service est fourni "tel quel", sans garantie de disponibilité 24/7. En particulier, l'IA en ligne dépend de fournisseurs tiers (Emergent, OpenAI, etc.) dont une indisponibilité ponctuelle ne saurait engager notre responsabilité.</p>
    <H>6. Limitation de responsabilité</H>
    <p>L'éditeur ne peut être tenu responsable des dommages indirects (perte de données, manque à gagner) résultant de l'utilisation du Service. Tu utilises le code généré sous ta seule responsabilité — pense à le relire avant de le mettre en production.</p>
    <H>7. Résiliation</H>
    <p>Tu peux supprimer ton compte à tout moment depuis ton profil. La suppression est irréversible et efface l'intégralité de tes données dans les 24h.</p>
    <H>8. Modification des CGU</H>
    <p>Les présentes CGU peuvent évoluer. Toute modification substantielle te sera notifiée par email à l'adresse associée à ton compte.</p>
    <H>9. Loi applicable</H>
    <p>Les présentes CGU sont régies par le droit français. Tout litige relèvera des tribunaux compétents.</p>
  </div>
);

const Privacy = () => (
  <div data-testid="legal-privacy" className="space-y-3">
    <H>1. Données collectées</H>
    <ul className="list-disc pl-5 space-y-1">
      <li><b>Compte</b> : email, nom (optionnel), mot de passe (haché bcrypt — jamais en clair).</li>
      <li><b>Projets</b> : descriptions, code généré, fichiers exportés.</li>
      <li><b>Sessions</b> : token de session, date de connexion, dernière activité.</li>
      <li><b>Logs techniques</b> : erreurs d'authentification (kind + détail anonymisé), pour la sécurité.</li>
    </ul>
    <H>2. Finalités</H>
    <p>Les données servent uniquement à fournir le Service (auth, génération, sauvegarde de tes projets). <b>Aucun usage publicitaire, aucune revente à des tiers.</b></p>
    <H>3. Hébergement & sous-traitants</H>
    <ul className="list-disc pl-5 space-y-1">
      <li>Hébergement principal : Emergent (Kubernetes en UE / US selon la région).</li>
      <li>Base de données : MongoDB (chiffrement au repos).</li>
      <li>Envoi d'emails : Resend (USA — clauses contractuelles types).</li>
      <li>IA en ligne : Emergent (proxy vers OpenAI / Anthropic / Google selon le modèle choisi).</li>
    </ul>
    <H>4. Tes droits (RGPD)</H>
    <ul className="list-disc pl-5 space-y-1">
      <li><b>Accès</b> : télécharge un export complet depuis ton profil ("Télécharger mes données").</li>
      <li><b>Rectification</b> : modifie email/nom/mot de passe depuis ton profil.</li>
      <li><b>Effacement</b> : "Supprimer mon compte" dans la zone dangereuse — irréversible et immédiat.</li>
      <li><b>Portabilité</b> : l'export JSON est réutilisable ailleurs.</li>
      <li><b>Opposition / réclamation</b> : contacte-nous (cf. CGU) ou la CNIL pour les résidents UE.</li>
    </ul>
    <H>5. Durée de conservation</H>
    <ul className="list-disc pl-5 space-y-1">
      <li>Compte actif : tant que tu utilises le Service.</li>
      <li>Sessions : 7 jours (auto-purge).</li>
      <li>Logs d'auth : 7 jours (auto-purge).</li>
      <li>Compte supprimé : effacement immédiat de toutes les données associées.</li>
    </ul>
    <H>6. Sécurité</H>
    <p>Mot de passe haché bcrypt + protection brute-force. HTTPS partout. Cookies HttpOnly + SameSite=None Secure. Sessions invalidées sur changement de mot de passe.</p>
  </div>
);

const Cookies = () => (
  <div data-testid="legal-cookies" className="space-y-3">
    <H>Cookies utilisés</H>
    <ul className="list-disc pl-5 space-y-1">
      <li><b>session_token</b> (HttpOnly) : maintien de ta session de connexion. Durée : 7 jours.</li>
    </ul>
    <H>localStorage</H>
    <ul className="list-disc pl-5 space-y-1">
      <li><b>session_token</b> (fallback) : même rôle que le cookie, utile si ton navigateur bloque les cookies cross-site.</li>
      <li><b>codeforge_last_email</b> : pré-remplit ton email à la prochaine visite.</li>
    </ul>
    <H>Pas de tracking</H>
    <p>Aucun cookie tiers, aucun pixel publicitaire, aucune analytique externe (Google Analytics & co). Tes données ne sont jamais partagées.</p>
  </div>
);
