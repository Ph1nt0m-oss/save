# 🚀 Installation Rapide DeepSeek Coder

## Installation en 2 minutes

```bash
# 1. Installer DeepSeek Coder (meilleur pour le code qu'Emergent)
ollama pull deepseek-coder:33b

# 2. Vérifier l'installation
ollama list

# 3. Tester
ollama run deepseek-coder:33b "Crée une fonction Python pour calculer Fibonacci"

# ✅ Si ça répond, c'est installé !
```

## Démarrer Ollama

```bash
# Lancer le serveur Ollama
ollama serve

# Laisser tourner en arrière-plan
```

## Configurer CodeForge

```bash
# Vérifier que CodeForge utilise DeepSeek
cat /app/backend/.env | grep OLLAMA_MODEL

# Devrait afficher:
# OLLAMA_MODEL=deepseek-coder:33b
```

## Redémarrer CodeForge

```bash
cd /app/backend
sudo supervisorctl restart backend
```

## ✅ C'est tout !

CodeForge utilise maintenant **DeepSeek Coder**, bien meilleur qu'Emergent pour la création de code.
