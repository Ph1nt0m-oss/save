# 🤖 Installation IA Locale Gratuite (Ollama + Llama)

## ✨ Solution 100% Gratuite Sans Limites

Ollama vous permet d'exécuter des IA puissantes **localement** sur votre ordinateur :
- ✅ **Gratuit** : Aucun coût
- ✅ **Illimité** : Pas de limite d'utilisation
- ✅ **Privé** : Vos données restent sur votre machine
- ✅ **Offline** : Fonctionne sans internet

---

## 📥 Installation Rapide

### Windows

```powershell
# Télécharger depuis le site officiel
https://ollama.com/download/windows

# Ou avec winget
winget install Ollama.Ollama
```

### macOS

```bash
# Télécharger depuis le site
https://ollama.com/download/mac

# Ou avec Homebrew
brew install ollama
```

### Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

---

## 🚀 Démarrage

### 1. Lancer Ollama

```bash
# Lance le serveur Ollama (port 11434 par défaut)
ollama serve
```

### 2. Télécharger un Modèle

**DeepSeek Coder (RECOMMANDÉ pour CodeForge - Meilleur pour le code)**
```bash
ollama pull deepseek-coder:33b
```

**Llama 3.3 (Bon pour le chat général)**
```bash
ollama pull llama3.3
```

**Mistral (Alternative)**
```bash
ollama pull mistral
```

**CodeLlama (Spécialisé code mais moins bon que DeepSeek)**
```bash
ollama pull codellama
```

### 3. Tester

```bash
# Test rapide
ollama run llama3.3

# Dans le chat, tapez votre question
>>> Bonjour ! Écris une fonction Python pour calculer Fibonacci
```

---

## 🔧 Configuration CodeForge

### 1. Vérifier qu'Ollama fonctionne

```bash
curl http://localhost:11434/api/tags
```

Vous devriez voir la liste de vos modèles.

### 2. Configurer le Backend

Éditez `/app/backend/.env` :

```env
# Ajouter cette ligne
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.3
```

### 3. Redémarrer le Backend

```bash
cd /app/backend
sudo supervisorctl restart backend

# Ou en local
uvicorn server:app --reload
```

### 4. Tester dans CodeForge

1. Ouvrir CodeForge
2. Créer un projet
3. Le chat utilisera automatiquement Ollama (gratuit et illimité!)

---

## 📊 Modèles Recommandés

| Modèle | Taille | RAM Min | Usage | Commande |
|--------|--------|---------|-------|----------|
| **Llama 3.3 8B** | 5GB | 8GB | Général, rapide | `ollama pull llama3.3` |
| **Mistral** | 4GB | 8GB | Créatif, français | `ollama pull mistral` |
| **CodeLlama** | 4GB | 8GB | Code uniquement | `ollama pull codellama` |
| **Llama 3.3 70B** | 40GB | 32GB | Très puissant | `ollama pull llama3.3:70b` |
| **DeepSeek Coder** | 7GB | 16GB | Expert code | `ollama pull deepseek-coder` |

---

## 🎯 Utilisation

### Commandes Utiles

```bash
# Lister les modèles installés
ollama list

# Supprimer un modèle
ollama rm mistral

# Voir les modèles disponibles
ollama list | grep available

# Mettre à jour un modèle
ollama pull llama3.3

# Arrêter Ollama
pkill ollama
```

### API Ollama

```bash
# Générer du texte
curl http://localhost:11434/api/generate -d '{
  \"model\": \"llama3.3\",
  \"prompt\": \"Écris une fonction Python\"
}'

# Chat
curl http://localhost:11434/api/chat -d '{
  \"model\": \"llama3.3\",
  \"messages\": [{\"role\": \"user\", \"content\": \"Bonjour!\"}]
}'
```

---

## 🔥 Performance

### Optimisation

**GPU NVIDIA (recommandé)**
```bash
# Ollama détecte automatiquement CUDA
# Vérifier l'utilisation GPU
nvidia-smi
```

**CPU Seulement**
```bash
# Utiliser un modèle plus petit
ollama pull llama3.3:7b-q4_0  # Version quantifiée
```

**RAM Limitée**
```bash
# Modèles légers
ollama pull phi3           # 2GB
ollama pull tinyllama      # 600MB
```

---

## 🌐 Alternative Gratuite (API Cloud)

Si vous ne pouvez pas installer Ollama localement :

### 1. Groq (Gratuit, Rapide)

```env
# Dans /app/backend/.env
GROQ_API_KEY=votre_clé_gratuite
GROQ_MODEL=llama3-70b-8192
```

Obtenir une clé gratuite : https://console.groq.com/

**Limites gratuites :**
- 14,400 requêtes/jour
- 600 requêtes/minute
- ✅ Assez pour un usage personnel !

### 2. Together.ai (Gratuit)

```env
TOGETHER_API_KEY=votre_clé_gratuite
TOGETHER_MODEL=mistralai/Mixtral-8x7B-Instruct-v0.1
```

Obtenir une clé : https://api.together.xyz/

---

## 🐛 Dépannage

### Ollama ne démarre pas

```bash
# Vérifier les logs
journalctl -u ollama -f

# Ou sur Windows
Get-EventLog -LogName Application -Source Ollama

# Réinstaller
curl -fsSL https://ollama.com/install.sh | sh
```

### Erreur de connexion

```bash
# Vérifier qu'Ollama tourne
curl http://localhost:11434/api/tags

# Redémarrer
pkill ollama
ollama serve
```

### Modèle trop lent

```bash
# Utiliser version quantifiée (plus rapide)
ollama pull llama3.3:7b-q4_0

# Ou modèle plus petit
ollama pull phi3
```

---

## ✅ Checklist Installation

- [ ] Ollama installé
- [ ] `ollama serve` en cours d'exécution
- [ ] Modèle téléchargé (`ollama pull llama3.3`)
- [ ] Test réussi (`ollama run llama3.3`)
- [ ] `.env` configuré avec OLLAMA_BASE_URL
- [ ] Backend redémarré
- [ ] Test dans CodeForge

---

## 🎉 Résultat

Une fois installé, vous avez :
- ✅ **IA locale gratuite** : Aucun coût
- ✅ **Illimité** : Pas de limite d'utilisation
- ✅ **Privé** : Vos projets restent confidentiels
- ✅ **Offline** : Fonctionne sans internet

**Créez autant d'applications que vous voulez, gratuitement ! 🚀**

---

## 📚 Ressources

- Site officiel : https://ollama.com
- Documentation : https://github.com/ollama/ollama
- Modèles : https://ollama.com/library
- Discord : https://discord.gg/ollama
