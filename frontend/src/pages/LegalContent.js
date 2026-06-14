// Translations of CGU / Privacy / Cookies across the 12 supported languages.
// Kept intentionally compact — same section structure everywhere so the UI
// renders identically regardless of locale.

const FR = {
  tab_cgu: "Conditions d'utilisation",
  tab_privacy: 'Confidentialité (RGPD)',
  tab_cookies: 'Cookies',
  title: 'Mentions légales',
  updated: 'Dernière mise à jour : 30 avril 2026',
  back: 'Retour',
  cgu: [
    { h: '1. Objet', p: 'CodeForge AI ("le Service") est une plateforme de génération assistée par IA d\'applications web, mobiles (PWA) et desktop (.exe).' },
    { h: '2. Compte utilisateur', p: "L'inscription est gratuite et ouverte aux personnes majeures (18 ans et +). Tu es responsable de la confidentialité de ton mot de passe et de toute activité sur ton compte." },
    { h: '3. Usage acceptable', p: "Tu t'engages à ne pas utiliser le Service pour : générer du code malveillant, harceler des tiers, violer des droits d'auteur, ou enfreindre toute loi applicable. Le Service peut suspendre tout compte enfreignant ces règles." },
    { h: '4. Propriété intellectuelle', p: 'Le code généré par l\'IA t\'appartient et tu peux l\'utiliser librement, y compris commercialement. La marque "CodeForge AI" et son interface restent la propriété de leurs auteurs.' },
    { h: '5. Disponibilité', p: 'Le Service est fourni "tel quel", sans garantie de disponibilité 24/7. En particulier, l\'IA en ligne dépend de fournisseurs tiers dont une indisponibilité ponctuelle ne saurait engager notre responsabilité.' },
    { h: '6. Limitation de responsabilité', p: "L'éditeur ne peut être tenu responsable des dommages indirects (perte de données, manque à gagner) résultant de l'utilisation du Service." },
    { h: '6 bis. Exports validés', p: "Lorsque ta demande d'export (ZIP, APK, EXE) est validée par la créatrice et que tu as récupéré une création conforme, la responsabilité de son usage te revient entièrement. Toute modification ultérieure — y compris transformation en outil dangereux, malveillant ou contraire à la loi — n'engage plus le Service ni la créatrice. Tu deviens seul responsable du code que tu détiens." },
    { h: '7. Résiliation', p: 'Tu peux supprimer ton compte à tout moment depuis ton profil. La suppression est irréversible et efface l\'intégralité de tes données dans les 24h.' },
    { h: '8. Modification des CGU', p: 'Les présentes CGU peuvent évoluer. Toute modification substantielle te sera notifiée par email.' },
    { h: '9. Loi applicable', p: 'Les présentes CGU sont régies par le droit français. Tout litige relèvera des tribunaux compétents.' },
  ],
  privacy: [
    { h: '1. Données collectées', ul: [
      '<b>Compte</b> : email, nom (optionnel), mot de passe (haché bcrypt — jamais en clair).',
      '<b>Projets</b> : descriptions, code généré, fichiers exportés.',
      '<b>Sessions</b> : token de session, date de connexion, dernière activité.',
      '<b>Logs techniques</b> : erreurs d\'authentification anonymisées, pour la sécurité.',
    ]},
    { h: '2. Finalités', p: 'Les données servent uniquement à fournir le Service. Aucun usage publicitaire, aucune revente à des tiers.' },
    { h: '3. Hébergement & sous-traitants', ul: [
      'Hébergement : Emergent (Kubernetes UE / US).',
      'Base de données : MongoDB (chiffrement au repos).',
      'Envoi d\'emails : Resend (USA — clauses contractuelles types).',
      'IA en ligne : Emergent (proxy OpenAI / Anthropic / Google).',
    ]},
    { h: '4. Tes droits (RGPD)', ul: [
      '<b>Accès</b> : télécharge un export depuis ton profil.',
      '<b>Rectification</b> : modifie email/nom/mot de passe.',
      '<b>Effacement</b> : "Supprimer mon compte" — immédiat.',
      '<b>Portabilité</b> : export JSON réutilisable.',
      '<b>Opposition / réclamation</b> : CNIL pour les résidents UE.',
    ]},
    { h: '5. Durée de conservation', ul: [
      'Compte actif : tant que tu utilises le Service.',
      'Sessions : 7 jours.',
      'Logs d\'auth : 7 jours.',
      'Compte supprimé : effacement immédiat.',
    ]},
    { h: '6. Sécurité', p: 'Mot de passe bcrypt + protection brute-force. HTTPS partout. Cookies HttpOnly + SameSite=None Secure. Sessions invalidées sur changement de mot de passe.' },
  ],
  cookies: [
    { h: 'Cookies utilisés', ul: [
      '<b>session_token</b> (HttpOnly) : maintien de ta session. Durée : 7 jours.',
    ]},
    { h: 'localStorage', ul: [
      '<b>session_token</b> (fallback) : même rôle que le cookie.',
      '<b>codeforge_last_email</b> : pré-remplit ton email.',
    ]},
    { h: 'Pas de tracking', p: 'Aucun cookie tiers, aucun pixel publicitaire, aucune analytique externe. Tes données ne sont jamais partagées.' },
  ],
};

const EN = {
  tab_cgu: 'Terms of Use', tab_privacy: 'Privacy (GDPR)', tab_cookies: 'Cookies',
  title: 'Legal notice', updated: 'Last updated: April 30, 2026', back: 'Back',
  cgu: [
    { h: '1. Purpose', p: 'CodeForge AI (the "Service") is an AI-assisted platform that generates web, mobile (PWA) and desktop (.exe) applications.' },
    { h: '2. Account', p: 'Sign-up is free and open to adults (18+). You are responsible for keeping your password confidential and for any activity under your account.' },
    { h: '3. Acceptable use', p: 'You agree not to use the Service to generate malicious code, harass third parties, violate copyrights, or break any applicable law. Violating accounts may be suspended.' },
    { h: '4. Intellectual property', p: 'AI-generated code belongs to you and can be used freely, including commercially. The "CodeForge AI" brand and UI remain the property of their authors.' },
    { h: '5. Availability', p: 'The Service is provided "as is", without guaranteed 24/7 availability. Third-party AI providers may have occasional downtime.' },
    { h: '6. Liability', p: 'The publisher is not liable for indirect damages (data loss, lost profits) arising from the use of the Service.' },
    { h: '7. Termination', p: 'You can delete your account at any time from your profile. Deletion is irreversible and wipes all your data within 24h.' },
    { h: '8. Changes', p: 'These terms may evolve. Substantial changes will be notified by email.' },
    { h: '9. Governing law', p: 'These terms are governed by French law. Any dispute will be settled by the competent courts.' },
  ],
  privacy: [
    { h: '1. Data collected', ul: [
      '<b>Account</b>: email, name (optional), password (bcrypt-hashed — never plaintext).',
      '<b>Projects</b>: descriptions, generated code, exported files.',
      '<b>Sessions</b>: session token, login date, last activity.',
      '<b>Technical logs</b>: anonymized auth errors, for security.',
    ]},
    { h: '2. Purposes', p: 'Data is used only to provide the Service. No advertising, no resale to third parties.' },
    { h: '3. Hosting & sub-processors', ul: [
      'Hosting: Emergent (Kubernetes EU / US).',
      'Database: MongoDB (encryption at rest).',
      'Emails: Resend (USA — standard contractual clauses).',
      'Online AI: Emergent (proxy to OpenAI / Anthropic / Google).',
    ]},
    { h: '4. Your rights (GDPR)', ul: [
      '<b>Access</b>: download a full export from your profile.',
      '<b>Rectification</b>: edit email/name/password.',
      '<b>Erasure</b>: "Delete my account" — immediate.',
      '<b>Portability</b>: the JSON export is reusable.',
      '<b>Objection / complaint</b>: contact us or your local DPA.',
    ]},
    { h: '5. Retention', ul: [
      'Active account: as long as you use the Service.',
      'Sessions: 7 days.',
      'Auth logs: 7 days.',
      'Deleted account: immediate erasure.',
    ]},
    { h: '6. Security', p: 'Bcrypt-hashed passwords + brute-force protection. HTTPS everywhere. HttpOnly + SameSite=None Secure cookies. Sessions invalidated on password change.' },
  ],
  cookies: [
    { h: 'Cookies used', ul: ['<b>session_token</b> (HttpOnly): keeps you signed in. Lifetime: 7 days.'] },
    { h: 'localStorage', ul: [
      '<b>session_token</b> (fallback): same role as the cookie.',
      '<b>codeforge_last_email</b>: pre-fills your email.',
    ]},
    { h: 'No tracking', p: 'No third-party cookies, no advertising pixels, no external analytics. Your data is never shared.' },
  ],
};

const ES = {
  tab_cgu: 'Condiciones de uso', tab_privacy: 'Privacidad (RGPD)', tab_cookies: 'Cookies',
  title: 'Aviso legal', updated: 'Última actualización: 30 de abril de 2026', back: 'Volver',
  cgu: [
    { h: '1. Objeto', p: 'CodeForge AI ("el Servicio") es una plataforma de generación asistida por IA de aplicaciones web, móviles (PWA) y de escritorio (.exe).' },
    { h: '2. Cuenta', p: 'El registro es gratuito y abierto a mayores de 18 años. Eres responsable de la confidencialidad de tu contraseña y de toda actividad en tu cuenta.' },
    { h: '3. Uso aceptable', p: 'Te comprometes a no usar el Servicio para generar código malicioso, acosar a terceros, violar derechos de autor o infringir la ley. El Servicio puede suspender toda cuenta infractora.' },
    { h: '4. Propiedad intelectual', p: 'El código generado por la IA te pertenece y puedes usarlo libremente, incluso con fines comerciales. La marca "CodeForge AI" sigue siendo propiedad de sus autores.' },
    { h: '5. Disponibilidad', p: 'El Servicio se ofrece "tal cual", sin garantía de disponibilidad 24/7. Los proveedores externos de IA pueden tener interrupciones ocasionales.' },
    { h: '6. Responsabilidad', p: 'El editor no se responsabiliza de daños indirectos derivados del uso del Servicio.' },
    { h: '7. Terminación', p: 'Puedes eliminar tu cuenta en cualquier momento desde tu perfil. La eliminación es irreversible y borra tus datos en 24h.' },
    { h: '8. Cambios', p: 'Estas condiciones pueden evolucionar. Se notificará por email cualquier cambio sustancial.' },
    { h: '9. Ley aplicable', p: 'Estas condiciones se rigen por la ley francesa. Los litigios competen a los tribunales competentes.' },
  ],
  privacy: [
    { h: '1. Datos recopilados', ul: [
      '<b>Cuenta</b>: email, nombre (opcional), contraseña (hash bcrypt — nunca en texto plano).',
      '<b>Proyectos</b>: descripciones, código generado, archivos exportados.',
      '<b>Sesiones</b>: token de sesión, fecha de conexión, última actividad.',
      '<b>Logs técnicos</b>: errores de autenticación anónimos, por seguridad.',
    ]},
    { h: '2. Finalidades', p: 'Los datos se usan solo para proveer el Servicio. Sin publicidad, sin reventa a terceros.' },
    { h: '3. Alojamiento y subencargados', ul: [
      'Alojamiento: Emergent (Kubernetes UE / EE. UU.).',
      'Base de datos: MongoDB (cifrado en reposo).',
      'Correos: Resend (EE. UU. — cláusulas contractuales tipo).',
      'IA en línea: Emergent (proxy a OpenAI / Anthropic / Google).',
    ]},
    { h: '4. Tus derechos (RGPD)', ul: [
      '<b>Acceso</b>: descarga un export desde tu perfil.',
      '<b>Rectificación</b>: modifica email/nombre/contraseña.',
      '<b>Supresión</b>: "Eliminar mi cuenta" — inmediato.',
      '<b>Portabilidad</b>: el export JSON es reutilizable.',
      '<b>Oposición / reclamación</b>: tu autoridad local de protección.',
    ]},
    { h: '5. Conservación', ul: [
      'Cuenta activa: mientras uses el Servicio.',
      'Sesiones: 7 días.',
      'Logs de auth: 7 días.',
      'Cuenta eliminada: borrado inmediato.',
    ]},
    { h: '6. Seguridad', p: 'Contraseña bcrypt + protección anti fuerza bruta. HTTPS en todas partes. Cookies HttpOnly + SameSite=None Secure. Sesiones invalidadas al cambiar de contraseña.' },
  ],
  cookies: [
    { h: 'Cookies usadas', ul: ['<b>session_token</b> (HttpOnly): mantiene tu sesión. Duración: 7 días.'] },
    { h: 'localStorage', ul: [
      '<b>session_token</b> (respaldo): mismo rol que la cookie.',
      '<b>codeforge_last_email</b>: rellena tu email.',
    ]},
    { h: 'Sin tracking', p: 'Ninguna cookie de terceros, ningún píxel publicitario, ninguna analítica externa. Tus datos nunca se comparten.' },
  ],
};

const PT = {
  tab_cgu: 'Termos de utilização', tab_privacy: 'Privacidade (RGPD)', tab_cookies: 'Cookies',
  title: 'Aviso legal', updated: 'Última atualização: 30 de abril de 2026', back: 'Voltar',
  cgu: [
    { h: '1. Objeto', p: 'CodeForge AI ("o Serviço") é uma plataforma de geração assistida por IA de aplicações web, móveis (PWA) e desktop (.exe).' },
    { h: '2. Conta', p: 'O registo é gratuito e aberto a maiores de 18 anos. És responsável pela confidencialidade da tua palavra-passe e por qualquer atividade na tua conta.' },
    { h: '3. Uso aceitável', p: 'Comprometes-te a não usar o Serviço para gerar código malicioso, assediar terceiros, violar direitos de autor ou infringir a lei. Contas infratoras podem ser suspensas.' },
    { h: '4. Propriedade intelectual', p: 'O código gerado pela IA pertence-te e podes usá-lo livremente, mesmo comercialmente. A marca "CodeForge AI" continua a ser propriedade dos seus autores.' },
    { h: '5. Disponibilidade', p: 'O Serviço é fornecido "tal como está", sem garantia de disponibilidade 24/7. Fornecedores externos podem ter indisponibilidades ocasionais.' },
    { h: '6. Responsabilidade', p: 'O editor não se responsabiliza por danos indiretos decorrentes do uso do Serviço.' },
    { h: '7. Rescisão', p: 'Podes eliminar a tua conta a qualquer momento a partir do perfil. A eliminação é irreversível em 24h.' },
    { h: '8. Alterações', p: 'Estes termos podem evoluir. Alterações substanciais serão notificadas por email.' },
    { h: '9. Lei aplicável', p: 'Estes termos regem-se pela lei francesa. Qualquer litígio será decidido pelos tribunais competentes.' },
  ],
  privacy: [
    { h: '1. Dados recolhidos', ul: [
      '<b>Conta</b>: email, nome (opcional), palavra-passe (hash bcrypt — nunca em claro).',
      '<b>Projetos</b>: descrições, código gerado, ficheiros exportados.',
      '<b>Sessões</b>: token de sessão, data de ligação, última atividade.',
      '<b>Logs técnicos</b>: erros de autenticação anónimos, por segurança.',
    ]},
    { h: '2. Finalidades', p: 'Os dados servem apenas para fornecer o Serviço. Sem publicidade, sem revenda a terceiros.' },
    { h: '3. Alojamento e subcontratantes', ul: [
      'Alojamento: Emergent (Kubernetes UE / EUA).',
      'Base de dados: MongoDB (cifragem em repouso).',
      'Emails: Resend (EUA — cláusulas contratuais tipo).',
      'IA online: Emergent (proxy para OpenAI / Anthropic / Google).',
    ]},
    { h: '4. Os teus direitos (RGPD)', ul: [
      '<b>Acesso</b>: transfere um export do teu perfil.',
      '<b>Retificação</b>: altera email/nome/palavra-passe.',
      '<b>Apagamento</b>: "Eliminar a minha conta" — imediato.',
      '<b>Portabilidade</b>: o export JSON é reutilizável.',
      '<b>Oposição / reclamação</b>: autoridade local de proteção.',
    ]},
    { h: '5. Conservação', ul: [
      'Conta ativa: enquanto usares o Serviço.',
      'Sessões: 7 dias.',
      'Logs de auth: 7 dias.',
      'Conta eliminada: apagamento imediato.',
    ]},
    { h: '6. Segurança', p: 'Palavra-passe bcrypt + proteção contra força bruta. HTTPS em todo o lado. Cookies HttpOnly + SameSite=None Secure. Sessões invalidadas ao mudar de palavra-passe.' },
  ],
  cookies: [
    { h: 'Cookies usados', ul: ['<b>session_token</b> (HttpOnly): mantém a sessão. Duração: 7 dias.'] },
    { h: 'localStorage', ul: [
      '<b>session_token</b> (fallback): mesmo papel que o cookie.',
      '<b>codeforge_last_email</b>: preenche o teu email.',
    ]},
    { h: 'Sem tracking', p: 'Nenhum cookie de terceiros, nenhum pixel publicitário, nenhuma analítica externa. Os teus dados nunca são partilhados.' },
  ],
};

const DE = {
  tab_cgu: 'Nutzungsbedingungen', tab_privacy: 'Datenschutz (DSGVO)', tab_cookies: 'Cookies',
  title: 'Rechtliche Hinweise', updated: 'Letzte Aktualisierung: 30. April 2026', back: 'Zurück',
  cgu: [
    { h: '1. Zweck', p: 'CodeForge AI ("der Dienst") ist eine KI-gestützte Plattform zur Erstellung von Web-, Mobile- (PWA) und Desktop-Anwendungen (.exe).' },
    { h: '2. Konto', p: 'Die Registrierung ist kostenlos und offen für volljährige Personen (18+). Du bist für die Vertraulichkeit deines Passworts und alle Kontoaktivitäten verantwortlich.' },
    { h: '3. Zulässige Nutzung', p: 'Du verpflichtest dich, den Dienst nicht zu nutzen, um schädlichen Code zu generieren, Dritte zu belästigen, Urheberrechte zu verletzen oder geltendes Recht zu brechen. Verstoßende Konten können gesperrt werden.' },
    { h: '4. Geistiges Eigentum', p: 'Der von der KI generierte Code gehört dir und darf frei verwendet werden, auch kommerziell. Die Marke "CodeForge AI" bleibt Eigentum ihrer Autoren.' },
    { h: '5. Verfügbarkeit', p: 'Der Dienst wird "wie gesehen" bereitgestellt, ohne Garantie für 24/7-Verfügbarkeit. Externe KI-Anbieter können gelegentlich ausfallen.' },
    { h: '6. Haftung', p: 'Der Anbieter haftet nicht für mittelbare Schäden aus der Nutzung des Dienstes.' },
    { h: '7. Kündigung', p: 'Du kannst dein Konto jederzeit im Profil löschen. Die Löschung ist unwiderruflich und erfolgt innerhalb von 24h.' },
    { h: '8. Änderungen', p: 'Diese Bedingungen können sich ändern. Wesentliche Änderungen werden per E-Mail mitgeteilt.' },
    { h: '9. Anwendbares Recht', p: 'Es gilt französisches Recht. Gerichtsstand ist das zuständige französische Gericht.' },
  ],
  privacy: [
    { h: '1. Erhobene Daten', ul: [
      '<b>Konto</b>: E-Mail, Name (optional), Passwort (bcrypt-gehasht — nie im Klartext).',
      '<b>Projekte</b>: Beschreibungen, generierter Code, exportierte Dateien.',
      '<b>Sitzungen</b>: Session-Token, Login-Datum, letzte Aktivität.',
      '<b>Technische Logs</b>: anonymisierte Auth-Fehler, aus Sicherheitsgründen.',
    ]},
    { h: '2. Zwecke', p: 'Die Daten dienen ausschließlich dem Betrieb des Dienstes. Keine Werbung, kein Weiterverkauf.' },
    { h: '3. Hosting & Auftragsverarbeiter', ul: [
      'Hosting: Emergent (Kubernetes EU / USA).',
      'Datenbank: MongoDB (Verschlüsselung ruhend).',
      'E-Mails: Resend (USA — Standardvertragsklauseln).',
      'Online-KI: Emergent (Proxy zu OpenAI / Anthropic / Google).',
    ]},
    { h: '4. Deine Rechte (DSGVO)', ul: [
      '<b>Auskunft</b>: Export im Profil herunterladen.',
      '<b>Berichtigung</b>: E-Mail/Name/Passwort ändern.',
      '<b>Löschung</b>: "Konto löschen" — sofort.',
      '<b>Übertragbarkeit</b>: der JSON-Export ist wiederverwendbar.',
      '<b>Widerspruch / Beschwerde</b>: zuständige Datenschutzbehörde.',
    ]},
    { h: '5. Aufbewahrung', ul: [
      'Aktives Konto: solange du den Dienst nutzt.',
      'Sitzungen: 7 Tage.',
      'Auth-Logs: 7 Tage.',
      'Gelöschtes Konto: sofortige Löschung.',
    ]},
    { h: '6. Sicherheit', p: 'Bcrypt-Passwörter + Brute-Force-Schutz. HTTPS überall. HttpOnly + SameSite=None Secure Cookies. Sitzungen bei Passwortwechsel ungültig.' },
  ],
  cookies: [
    { h: 'Verwendete Cookies', ul: ['<b>session_token</b> (HttpOnly): hält deine Sitzung. Dauer: 7 Tage.'] },
    { h: 'localStorage', ul: [
      '<b>session_token</b> (Fallback): dieselbe Rolle wie das Cookie.',
      '<b>codeforge_last_email</b>: füllt deine E-Mail vor.',
    ]},
    { h: 'Kein Tracking', p: 'Keine Drittanbieter-Cookies, keine Werbepixel, keine externe Analyse. Deine Daten werden nie geteilt.' },
  ],
};

const NL = {
  tab_cgu: 'Gebruiksvoorwaarden', tab_privacy: 'Privacy (AVG)', tab_cookies: 'Cookies',
  title: 'Juridische kennisgeving', updated: 'Laatst bijgewerkt: 30 april 2026', back: 'Terug',
  cgu: [
    { h: '1. Doel', p: 'CodeForge AI ("de Dienst") is een AI-platform voor het genereren van web-, mobiele (PWA) en desktop-applicaties (.exe).' },
    { h: '2. Account', p: 'Aanmelden is gratis en open voor meerderjarigen (18+). Je bent verantwoordelijk voor de vertrouwelijkheid van je wachtwoord en alle activiteit op je account.' },
    { h: '3. Acceptabel gebruik', p: 'Je gebruikt de Dienst niet om kwaadaardige code te genereren, anderen lastig te vallen, auteursrechten te schenden of de wet te overtreden. Overtredende accounts kunnen worden opgeschort.' },
    { h: '4. Intellectueel eigendom', p: 'De door AI gegenereerde code is van jou en mag vrij gebruikt worden, ook commercieel. Het merk "CodeForge AI" blijft eigendom van de auteurs.' },
    { h: '5. Beschikbaarheid', p: 'De Dienst wordt "as is" geleverd, zonder 24/7-garantie. Externe AI-leveranciers kunnen tijdelijk uitvallen.' },
    { h: '6. Aansprakelijkheid', p: 'De uitgever is niet aansprakelijk voor indirecte schade uit het gebruik van de Dienst.' },
    { h: '7. Beëindiging', p: 'Je kunt je account altijd verwijderen vanuit je profiel. Verwijdering is onomkeerbaar binnen 24u.' },
    { h: '8. Wijzigingen', p: 'Deze voorwaarden kunnen veranderen. Ingrijpende wijzigingen worden per e-mail gemeld.' },
    { h: '9. Toepasselijk recht', p: 'Deze voorwaarden vallen onder Frans recht. Geschillen worden beslecht door de bevoegde rechtbank.' },
  ],
  privacy: [
    { h: '1. Verzamelde gegevens', ul: [
      '<b>Account</b>: e-mail, naam (optioneel), wachtwoord (bcrypt-hash — nooit in klare tekst).',
      '<b>Projecten</b>: beschrijvingen, gegenereerde code, geëxporteerde bestanden.',
      '<b>Sessies</b>: sessietoken, logindatum, laatste activiteit.',
      '<b>Technische logs</b>: geanonimiseerde auth-fouten, voor veiligheid.',
    ]},
    { h: '2. Doeleinden', p: 'Gegevens worden alleen gebruikt om de Dienst te leveren. Geen reclame, geen doorverkoop.' },
    { h: '3. Hosting & subverwerkers', ul: [
      'Hosting: Emergent (Kubernetes EU / VS).',
      'Database: MongoDB (encryptie in rust).',
      'E-mails: Resend (VS — modelbepalingen).',
      'Online-AI: Emergent (proxy naar OpenAI / Anthropic / Google).',
    ]},
    { h: '4. Jouw rechten (AVG)', ul: [
      '<b>Inzage</b>: download een export uit je profiel.',
      '<b>Rectificatie</b>: wijzig e-mail/naam/wachtwoord.',
      '<b>Wissing</b>: "Account verwijderen" — direct.',
      '<b>Overdraagbaarheid</b>: de JSON-export is herbruikbaar.',
      '<b>Bezwaar / klacht</b>: lokale toezichthouder.',
    ]},
    { h: '5. Bewaartermijn', ul: [
      'Actief account: zolang je de Dienst gebruikt.',
      'Sessies: 7 dagen.',
      'Auth-logs: 7 dagen.',
      'Verwijderd account: direct gewist.',
    ]},
    { h: '6. Beveiliging', p: 'Bcrypt-wachtwoorden + brute-force-bescherming. HTTPS overal. HttpOnly + SameSite=None Secure cookies. Sessies ongeldig bij wachtwoordwissel.' },
  ],
  cookies: [
    { h: 'Gebruikte cookies', ul: ['<b>session_token</b> (HttpOnly): houdt je ingelogd. Duur: 7 dagen.'] },
    { h: 'localStorage', ul: [
      '<b>session_token</b> (fallback): zelfde rol als de cookie.',
      '<b>codeforge_last_email</b>: vult je e-mail vooraf in.',
    ]},
    { h: 'Geen tracking', p: 'Geen cookies van derden, geen advertentiepixels, geen externe analytics. Je gegevens worden nooit gedeeld.' },
  ],
};

const RU = {
  tab_cgu: 'Условия использования', tab_privacy: 'Конфиденциальность (GDPR)', tab_cookies: 'Cookies',
  title: 'Юридическая информация', updated: 'Последнее обновление: 30 апреля 2026', back: 'Назад',
  cgu: [
    { h: '1. Предмет', p: 'CodeForge AI ("Сервис") — платформа для создания веб-, мобильных (PWA) и настольных приложений (.exe) с помощью ИИ.' },
    { h: '2. Учётная запись', p: 'Регистрация бесплатна и открыта для совершеннолетних (18+). Вы отвечаете за конфиденциальность пароля и активность в аккаунте.' },
    { h: '3. Допустимое использование', p: 'Вы не будете использовать Сервис для создания вредоносного кода, преследования, нарушения авторских прав или закона. Нарушителей блокируют.' },
    { h: '4. Интеллектуальная собственность', p: 'Сгенерированный ИИ код принадлежит вам, может использоваться свободно, в т.ч. коммерчески. Бренд "CodeForge AI" остаётся собственностью авторов.' },
    { h: '5. Доступность', p: 'Сервис предоставляется "как есть", без гарантии доступности 24/7. У внешних ИИ-провайдеров возможны перебои.' },
    { h: '6. Ответственность', p: 'Издатель не отвечает за косвенный ущерб от использования Сервиса.' },
    { h: '7. Прекращение', p: 'Вы можете удалить аккаунт в любое время в профиле. Удаление необратимо в течение 24 ч.' },
    { h: '8. Изменения', p: 'Условия могут меняться. О существенных изменениях уведомим по email.' },
    { h: '9. Применимое право', p: 'Условия регулируются правом Франции. Споры — в компетентных судах.' },
  ],
  privacy: [
    { h: '1. Собираемые данные', ul: [
      '<b>Аккаунт</b>: email, имя (необязательно), пароль (bcrypt — никогда в открытом виде).',
      '<b>Проекты</b>: описания, сгенерированный код, экспортированные файлы.',
      '<b>Сессии</b>: токен, дата входа, последняя активность.',
      '<b>Техлоги</b>: обезличенные ошибки авторизации (безопасность).',
    ]},
    { h: '2. Цели', p: 'Данные используются только для работы Сервиса. Никакой рекламы и перепродажи.' },
    { h: '3. Хостинг и субпроцессоры', ul: [
      'Хостинг: Emergent (Kubernetes EU / US).',
      'БД: MongoDB (шифрование в покое).',
      'Email: Resend (США — стандартные договорные оговорки).',
      'ИИ онлайн: Emergent (прокси OpenAI / Anthropic / Google).',
    ]},
    { h: '4. Ваши права (GDPR)', ul: [
      '<b>Доступ</b>: скачайте экспорт в профиле.',
      '<b>Исправление</b>: измените email/имя/пароль.',
      '<b>Удаление</b>: "Удалить аккаунт" — мгновенно.',
      '<b>Переносимость</b>: JSON-экспорт переиспользуемый.',
      '<b>Возражение/жалоба</b>: локальный надзорный орган.',
    ]},
    { h: '5. Сроки хранения', ul: [
      'Активный аккаунт: пока пользуетесь.',
      'Сессии: 7 дней.',
      'Логи авторизации: 7 дней.',
      'Удалённый аккаунт: немедленно.',
    ]},
    { h: '6. Безопасность', p: 'Пароли bcrypt + защита от брутфорса. HTTPS везде. HttpOnly + SameSite=None Secure. Сессии сбрасываются при смене пароля.' },
  ],
  cookies: [
    { h: 'Используемые cookie', ul: ['<b>session_token</b> (HttpOnly): держит сессию. Срок: 7 дней.'] },
    { h: 'localStorage', ul: [
      '<b>session_token</b> (резерв): та же роль, что и cookie.',
      '<b>codeforge_last_email</b>: подставляет ваш email.',
    ]},
    { h: 'Без трекинга', p: 'Никаких сторонних cookie, рекламных пикселей, внешней аналитики. Данные не передаются.' },
  ],
};

const ZH = {
  tab_cgu: '使用条款', tab_privacy: '隐私 (GDPR)', tab_cookies: 'Cookies',
  title: '法律声明', updated: '最后更新：2026年4月30日', back: '返回',
  cgu: [
    { h: '1. 目的', p: 'CodeForge AI（"本服务"）是一个 AI 辅助生成 Web、移动 (PWA) 和桌面 (.exe) 应用的平台。' },
    { h: '2. 账户', p: '注册免费，面向 18 岁及以上用户。您对密码保密及账户活动负责。' },
    { h: '3. 合理使用', p: '您承诺不使用本服务生成恶意代码、骚扰他人、侵犯版权或违法。违规账户将被封禁。' },
    { h: '4. 知识产权', p: 'AI 生成的代码归您所有，可自由使用（含商业）。"CodeForge AI" 品牌归作者所有。' },
    { h: '5. 可用性', p: '本服务按"现状"提供，不保证 7×24 可用。第三方 AI 偶有中断。' },
    { h: '6. 责任', p: '发行方不对因使用本服务产生的间接损失负责。' },
    { h: '7. 终止', p: '您可随时在个人资料中删除账户，24 小时内彻底清除数据。' },
    { h: '8. 变更', p: '条款可能更新，重大变更将通过邮件通知。' },
    { h: '9. 适用法律', p: '本条款适用法国法律，由法国有管辖权的法院处理争议。' },
  ],
  privacy: [
    { h: '1. 收集的数据', ul: [
      '<b>账户</b>：邮箱、姓名（可选）、密码（bcrypt 哈希——从不明文）。',
      '<b>项目</b>：描述、生成的代码、导出文件。',
      '<b>会话</b>：会话令牌、登录时间、最近活动。',
      '<b>技术日志</b>：匿名化的认证错误（用于安全）。',
    ]},
    { h: '2. 目的', p: '数据仅用于提供服务。无广告，不转售。' },
    { h: '3. 托管及分包商', ul: [
      '托管：Emergent（Kubernetes 欧盟/美国）。',
      '数据库：MongoDB（静态加密）。',
      '邮件：Resend（美国——标准合同条款）。',
      '在线 AI：Emergent（代理到 OpenAI / Anthropic / Google）。',
    ]},
    { h: '4. 您的权利 (GDPR)', ul: [
      '<b>访问</b>：在个人资料中下载导出。',
      '<b>更正</b>：修改邮箱/姓名/密码。',
      '<b>删除</b>："删除账户"——立即执行。',
      '<b>可移植</b>：JSON 导出可复用。',
      '<b>反对/投诉</b>：当地数据保护机构。',
    ]},
    { h: '5. 保留期', ul: [
      '活跃账户：使用期间。',
      '会话：7 天。',
      '认证日志：7 天。',
      '已删除账户：立即擦除。',
    ]},
    { h: '6. 安全', p: 'bcrypt 密码 + 防暴力破解。全站 HTTPS。HttpOnly + SameSite=None Secure Cookie。改密后会话失效。' },
  ],
  cookies: [
    { h: '使用的 Cookie', ul: ['<b>session_token</b> (HttpOnly)：保持登录。有效期：7 天。'] },
    { h: 'localStorage', ul: [
      '<b>session_token</b>（备用）：同 Cookie 作用。',
      '<b>codeforge_last_email</b>：预填您的邮箱。',
    ]},
    { h: '无追踪', p: '无第三方 Cookie、无广告像素、无外部分析。您的数据从不共享。' },
  ],
};

// Traditional Chinese — reuse ZH structure with minor character changes.
const ZH_TW = {
  ...ZH,
  tab_cgu: '使用條款', tab_privacy: '隱私 (GDPR)', tab_cookies: 'Cookies',
  title: '法律聲明', updated: '最後更新：2026年4月30日', back: '返回',
};

const HI = {
  tab_cgu: 'उपयोग की शर्तें', tab_privacy: 'गोपनीयता (GDPR)', tab_cookies: 'कुकीज़',
  title: 'कानूनी सूचना', updated: 'आख़िरी अपडेट: 30 अप्रैल 2026', back: 'वापस',
  cgu: [
    { h: '1. उद्देश्य', p: 'CodeForge AI ("सेवा") वेब, मोबाइल (PWA) और डेस्कटॉप (.exe) ऐप्स बनाने का AI-सहायक प्लेटफ़ॉर्म है।' },
    { h: '2. खाता', p: 'साइन-अप मुफ़्त है और 18+ के लिए खुला है। आप अपने पासवर्ड की गोपनीयता और खाते की गतिविधि के लिए ज़िम्मेदार हैं।' },
    { h: '3. स्वीकार्य उपयोग', p: 'आप सेवा का उपयोग दुर्भावनापूर्ण कोड बनाने, उत्पीड़न, कॉपीराइट उल्लंघन या कानून तोड़ने के लिए नहीं करेंगे। उल्लंघन पर खाता निलंबित होगा।' },
    { h: '4. बौद्धिक संपदा', p: 'AI-जनित कोड आपका है और व्यावसायिक रूप से भी स्वतंत्र रूप से उपयोग्य है। "CodeForge AI" ब्रांड लेखकों की संपत्ति है।' },
    { h: '5. उपलब्धता', p: 'सेवा "जैसी है" आधार पर बिना 24/7 गारंटी के प्रदान की जाती है। बाहरी AI प्रदाता कभी-कभी बंद हो सकते हैं।' },
    { h: '6. दायित्व', p: 'प्रकाशक सेवा के उपयोग से होने वाले अप्रत्यक्ष नुकसान के लिए ज़िम्मेदार नहीं है।' },
    { h: '7. समाप्ति', p: 'आप प्रोफ़ाइल से किसी भी समय खाता हटा सकते हैं। हटाना अपरिवर्तनीय, 24 घंटे में।' },
    { h: '8. बदलाव', p: 'ये शर्तें बदल सकती हैं। महत्त्वपूर्ण बदलाव ईमेल से सूचित किए जाएँगे।' },
    { h: '9. लागू कानून', p: 'ये शर्तें फ़्रांसीसी क़ानून के अधीन हैं। विवाद सक्षम न्यायालय में निपटाए जाएँगे।' },
  ],
  privacy: [
    { h: '1. एकत्र किया गया डेटा', ul: [
      '<b>खाता</b>: ईमेल, नाम (वैकल्पिक), पासवर्ड (bcrypt हैश — कभी सादे रूप में नहीं)।',
      '<b>परियोजनाएँ</b>: विवरण, जनित कोड, निर्यात फ़ाइलें।',
      '<b>सत्र</b>: सत्र टोकन, लॉगिन तिथि, अंतिम गतिविधि।',
      '<b>तकनीकी लॉग</b>: गुमनाम प्रमाणीकरण त्रुटियाँ (सुरक्षा हेतु)।',
    ]},
    { h: '2. उद्देश्य', p: 'डेटा केवल सेवा प्रदान करने के लिए। कोई विज्ञापन, कोई पुनर्विक्रय नहीं।' },
    { h: '3. होस्टिंग व उप-प्रसंस्करणकर्ता', ul: [
      'होस्टिंग: Emergent (Kubernetes EU / US)।',
      'डेटाबेस: MongoDB (स्थैतिक एन्क्रिप्शन)।',
      'ईमेल: Resend (USA — मानक संविदा खंड)।',
      'ऑनलाइन AI: Emergent (OpenAI / Anthropic / Google को प्रॉक्सी)।',
    ]},
    { h: '4. आपके अधिकार (GDPR)', ul: [
      '<b>एक्सेस</b>: प्रोफ़ाइल से पूरा निर्यात डाउनलोड करें।',
      '<b>सुधार</b>: ईमेल/नाम/पासवर्ड संपादित करें।',
      '<b>मिटाना</b>: "खाता हटाएँ" — तुरंत।',
      '<b>स्थानांतरणीयता</b>: JSON निर्यात पुनः उपयोग्य।',
      '<b>आपत्ति / शिकायत</b>: स्थानीय DPA।',
    ]},
    { h: '5. प्रतिधारण', ul: [
      'सक्रिय खाता: उपयोग जारी रहने तक।',
      'सत्र: 7 दिन।',
      'प्रमाणीकरण लॉग: 7 दिन।',
      'हटाया गया खाता: तुरंत मिटाया गया।',
    ]},
    { h: '6. सुरक्षा', p: 'bcrypt पासवर्ड + ब्रूट-फ़ोर्स सुरक्षा। हर जगह HTTPS। HttpOnly + SameSite=None Secure कुकीज़। पासवर्ड बदलते ही सत्र अमान्य।' },
  ],
  cookies: [
    { h: 'उपयोग की गई कुकीज़', ul: ['<b>session_token</b> (HttpOnly): आपको लॉगिन रखती है। अवधि: 7 दिन।'] },
    { h: 'localStorage', ul: [
      '<b>session_token</b> (फ़ॉलबैक): वही भूमिका जो कुकी की।',
      '<b>codeforge_last_email</b>: आपका ईमेल पहले से भरती है।',
    ]},
    { h: 'कोई ट्रैकिंग नहीं', p: 'कोई तृतीय-पक्ष कुकी नहीं, कोई विज्ञापन पिक्सेल नहीं, कोई बाहरी विश्लेषण नहीं। आपका डेटा कभी साझा नहीं होता।' },
  ],
};

const BN = {
  tab_cgu: 'ব্যবহারের শর্তাবলী', tab_privacy: 'গোপনীয়তা (GDPR)', tab_cookies: 'কুকিজ',
  title: 'আইনি তথ্য', updated: 'সর্বশেষ আপডেট: 30 এপ্রিল 2026', back: 'ফেরত',
  cgu: [
    { h: '1. উদ্দেশ্য', p: 'CodeForge AI ("পরিষেবা") ওয়েব, মোবাইল (PWA) ও ডেস্কটপ (.exe) অ্যাপ তৈরি করার AI-সহায়ক প্ল্যাটফর্ম।' },
    { h: '2. অ্যাকাউন্ট', p: 'নিবন্ধন বিনামূল্যে এবং 18+ এর জন্য উন্মুক্ত। পাসওয়ার্ডের গোপনীয়তা ও অ্যাকাউন্টের কার্যকলাপের জন্য আপনি দায়ী।' },
    { h: '3. গ্রহণযোগ্য ব্যবহার', p: 'ক্ষতিকর কোড তৈরি, হয়রানি, কপিরাইট লঙ্ঘন বা আইন ভাঙতে পরিষেবা ব্যবহার করবেন না। লঙ্ঘনকারী অ্যাকাউন্ট স্থগিত হতে পারে।' },
    { h: '4. বুদ্ধিবৃত্তিক সম্পত্তি', p: 'AI-জনিত কোড আপনার; বাণিজ্যিক ব্যবহারসহ মুক্তভাবে ব্যবহার্য। "CodeForge AI" ব্র্যান্ড লেখকদের সম্পত্তি।' },
    { h: '5. প্রাপ্যতা', p: 'পরিষেবা "যেমন আছে" সরবরাহ করা হয়, 24/7 নিশ্চয়তা ছাড়া। বাহ্যিক AI প্রোভাইডার মাঝেমধ্যে অচল হতে পারে।' },
    { h: '6. দায়', p: 'পরিষেবা ব্যবহারের পরোক্ষ ক্ষতির জন্য প্রকাশক দায়ী নয়।' },
    { h: '7. সমাপ্তি', p: 'আপনি যে কোনো সময় প্রোফাইল থেকে অ্যাকাউন্ট মুছতে পারেন। মুছে ফেলা অপরিবর্তনীয়, 24 ঘণ্টায়।' },
    { h: '8. পরিবর্তন', p: 'শর্তাবলী পরিবর্তিত হতে পারে। গুরুত্বপূর্ণ পরিবর্তন ইমেইলে জানানো হবে।' },
    { h: '9. প্রযোজ্য আইন', p: 'ফরাসি আইন প্রযোজ্য। বিরোধ যোগ্য আদালতে নিষ্পত্তি।' },
  ],
  privacy: [
    { h: '1. সংগৃহীত তথ্য', ul: [
      '<b>অ্যাকাউন্ট</b>: ইমেইল, নাম (ঐচ্ছিক), পাসওয়ার্ড (bcrypt হ্যাশ — কখনো প্লেইনটেক্সট নয়)।',
      '<b>প্রকল্প</b>: বিবরণ, জনরেট কোড, রপ্তানি ফাইল।',
      '<b>সেশন</b>: সেশন টোকেন, লগইন তারিখ, সর্বশেষ কার্যকলাপ।',
      '<b>টেকনিক্যাল লগ</b>: বেনামী অথ ত্রুটি (নিরাপত্তা)।',
    ]},
    { h: '2. উদ্দেশ্য', p: 'ডেটা শুধু পরিষেবা প্রদানে ব্যবহৃত। কোনো বিজ্ঞাপন বা পুনর্বিক্রয় নেই।' },
    { h: '3. হোস্টিং ও উপ-প্রসেসর', ul: [
      'হোস্টিং: Emergent (Kubernetes EU / US)।',
      'ডিবি: MongoDB (স্ট্যাটিক এনক্রিপশন)।',
      'ইমেইল: Resend (USA — স্ট্যান্ডার্ড চুক্তি ধারা)।',
      'অনলাইন AI: Emergent (OpenAI / Anthropic / Google এ প্রক্সি)।',
    ]},
    { h: '4. আপনার অধিকার (GDPR)', ul: [
      '<b>অ্যাক্সেস</b>: প্রোফাইল থেকে রপ্তানি ডাউনলোড।',
      '<b>সংশোধন</b>: ইমেইল/নাম/পাসওয়ার্ড পরিবর্তন।',
      '<b>মুছে ফেলা</b>: "অ্যাকাউন্ট মুছুন" — তাৎক্ষণিক।',
      '<b>পোর্টেবিলিটি</b>: JSON এক্সপোর্ট পুনর্ব্যবহারযোগ্য।',
      '<b>আপত্তি/অভিযোগ</b>: স্থানীয় ডেটা সুরক্ষা কর্তৃপক্ষ।',
    ]},
    { h: '5. সংরক্ষণকাল', ul: [
      'সক্রিয় অ্যাকাউন্ট: ব্যবহারের সময় পর্যন্ত।',
      'সেশন: 7 দিন।',
      'অথ লগ: 7 দিন।',
      'মুছে ফেলা অ্যাকাউন্ট: অবিলম্বে মুছে যায়।',
    ]},
    { h: '6. নিরাপত্তা', p: 'bcrypt পাসওয়ার্ড + ব্রুট-ফোর্স সুরক্ষা। সর্বত্র HTTPS। HttpOnly + SameSite=None Secure কুকি। পাসওয়ার্ড বদলালে সেশন বাতিল।' },
  ],
  cookies: [
    { h: 'ব্যবহৃত কুকি', ul: ['<b>session_token</b> (HttpOnly): আপনাকে লগইন রাখে। মেয়াদ: 7 দিন।'] },
    { h: 'localStorage', ul: [
      '<b>session_token</b> (ফ্যালব্যাক): কুকির মতো একই ভূমিকা।',
      '<b>codeforge_last_email</b>: আপনার ইমেইল আগেই পূরণ করে।',
    ]},
    { h: 'কোনো ট্র্যাকিং নেই', p: 'কোনো তৃতীয়-পক্ষ কুকি, বিজ্ঞাপন পিক্সেল বা বাহ্যিক অ্যানালিটিক্স নেই। আপনার ডেটা কখনো শেয়ার করা হয় না।' },
  ],
};

const UR = {
  tab_cgu: 'استعمال کی شرائط', tab_privacy: 'رازداری (GDPR)', tab_cookies: 'کوکیز',
  title: 'قانونی نوٹس', updated: 'آخری اپ ڈیٹ: 30 اپریل 2026', back: 'واپس',
  cgu: [
    { h: '1. مقصد', p: 'CodeForge AI ("سروس") AI کی مدد سے ویب، موبائل (PWA) اور ڈیسک ٹاپ (.exe) ایپس بنانے کا پلیٹ فارم ہے۔' },
    { h: '2. اکاؤنٹ', p: 'رجسٹریشن مفت اور 18+ کے لیے ہے۔ پاس ورڈ کی رازداری اور اکاؤنٹ کی سرگرمی کے آپ ذمہ دار ہیں۔' },
    { h: '3. قابلِ قبول استعمال', p: 'آپ نقصان دہ کوڈ، ہراسانی، کاپی رائٹ کی خلاف ورزی یا قانون کی خلاف ورزی کے لیے سروس استعمال نہیں کریں گے۔ خلاف ورزی پر اکاؤنٹ معطل ہو سکتا ہے۔' },
    { h: '4. دانشورانہ ملکیت', p: 'AI سے تیار شدہ کوڈ آپ کی ملکیت ہے اور تجارتی استعمال سمیت آزادانہ استعمال کیا جا سکتا ہے۔ "CodeForge AI" برانڈ اس کے مصنفین کی ملکیت ہے۔' },
    { h: '5. دستیابی', p: 'سروس "جیسی ہے" فراہم کی جاتی ہے، 24/7 دستیابی کی ضمانت کے بغیر۔ بیرونی AI فراہم کنندگان کبھی کبھار دستیاب نہ ہو سکیں۔' },
    { h: '6. ذمہ داری', p: 'ناشر سروس کے استعمال سے ہونے والے بالواسطہ نقصانات کا ذمہ دار نہیں ہے۔' },
    { h: '7. خاتمہ', p: 'آپ پروفائل سے کسی بھی وقت اکاؤنٹ حذف کر سکتے ہیں، 24 گھنٹوں میں ناقابلِ واپسی۔' },
    { h: '8. تبدیلیاں', p: 'شرائط بدل سکتی ہیں۔ اہم تبدیلیاں ای میل سے مطلع کی جائیں گی۔' },
    { h: '9. لاگو قانون', p: 'یہ شرائط فرانسیسی قانون کے تحت ہیں۔ تنازعات مجاز عدالتوں میں طے ہوں گے۔' },
  ],
  privacy: [
    { h: '1. جمع کردہ ڈیٹا', ul: [
      '<b>اکاؤنٹ</b>: ای میل، نام (اختیاری)، پاس ورڈ (bcrypt ہیش — کبھی پلین ٹیکسٹ نہیں)۔',
      '<b>پراجیکٹس</b>: تفصیلات، تیار کردہ کوڈ، ایکسپورٹ فائلز۔',
      '<b>سیشنز</b>: سیشن ٹوکن، لاگ ان تاریخ، آخری سرگرمی۔',
      '<b>تکنیکی لاگز</b>: گمنام توثیقی غلطیاں (سیکورٹی)۔',
    ]},
    { h: '2. مقاصد', p: 'ڈیٹا صرف سروس فراہم کرنے کے لیے۔ کوئی اشتہار یا فروخت نہیں۔' },
    { h: '3. ہوسٹنگ و ذیلی پروسیسرز', ul: [
      'ہوسٹنگ: Emergent (Kubernetes EU / US)۔',
      'ڈیٹا بیس: MongoDB (اسٹیٹک انکرپشن)۔',
      'ای میل: Resend (USA — معیاری معاہداتی شقیں)۔',
      'آن لائن AI: Emergent (OpenAI / Anthropic / Google پر پراکسی)۔',
    ]},
    { h: '4. آپ کے حقوق (GDPR)', ul: [
      '<b>رسائی</b>: پروفائل سے ایکسپورٹ ڈاؤن لوڈ کریں۔',
      '<b>تصحیح</b>: ای میل/نام/پاس ورڈ تبدیل کریں۔',
      '<b>حذف</b>: "اکاؤنٹ حذف کریں" — فوری۔',
      '<b>منتقلی</b>: JSON ایکسپورٹ دوبارہ قابلِ استعمال۔',
      '<b>اعتراض/شکایت</b>: مقامی ڈیٹا تحفظ ادارہ۔',
    ]},
    { h: '5. مدتِ برقرار', ul: [
      'فعال اکاؤنٹ: جب تک آپ استعمال کریں۔',
      'سیشنز: 7 دن۔',
      'توثیق لاگز: 7 دن۔',
      'حذف شدہ اکاؤنٹ: فوری مٹا دیا جاتا ہے۔',
    ]},
    { h: '6. سیکورٹی', p: 'bcrypt پاس ورڈز + بروٹ-فورس تحفظ۔ ہر جگہ HTTPS۔ HttpOnly + SameSite=None Secure کوکیز۔ پاس ورڈ تبدیلی پر سیشنز منسوخ۔' },
  ],
  cookies: [
    { h: 'استعمال ہونے والی کوکیز', ul: ['<b>session_token</b> (HttpOnly): آپ کو لاگ ان رکھتی ہے۔ مدت: 7 دن۔'] },
    { h: 'localStorage', ul: [
      '<b>session_token</b> (بیک اپ): کوکی جیسا ہی کردار۔',
      '<b>codeforge_last_email</b>: آپ کی ای میل پہلے سے بھرتی ہے۔',
    ]},
    { h: 'کوئی ٹریکنگ نہیں', p: 'کوئی تھرڈ پارٹی کوکی، اشتہاری پکسل یا بیرونی اینالٹکس نہیں۔ آپ کا ڈیٹا کبھی شیئر نہیں کیا جاتا۔' },
  ],
};

export const LEGAL_I18N = {
  fr: FR, en: EN, es: ES, pt: PT, de: DE, nl: NL, ru: RU,
  zh: ZH, 'zh-TW': ZH_TW, hi: HI, bn: BN, ur: UR,
};
