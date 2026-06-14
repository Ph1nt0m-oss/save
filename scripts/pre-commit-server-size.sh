#!/bin/bash
# iter124 — Pre-commit hook : bloque tout commit qui ferait grossir server.py au-delà du seuil.
# Installer : ln -s $(pwd)/scripts/pre-commit-server-size.sh .git/hooks/pre-commit
set -e

THRESHOLD=5500
SERVER="/app/backend/server.py"

if [ ! -f "$SERVER" ]; then
  exit 0
fi

LINES=$(wc -l < "$SERVER")
if [ "$LINES" -gt "$THRESHOLD" ]; then
  echo ""
  echo "❌ COMMIT BLOQUÉ — server.py = $LINES lignes (seuil $THRESHOLD)"
  echo ""
  echo "Refactore avant de commit :"
  echo "  1. Extrait des routes vers /app/backend/routes/ (pattern factory build_*_router)"
  echo "  2. Extrait des helpers vers /app/backend/services/"
  echo "  3. Models Pydantic à module-level (jamais 'from __future__ import annotations'"
  echo "     dans les fichiers de routes — voir iter122 regression)"
  echo ""
  echo "Pour bypasser temporairement (déconseillé) :"
  echo "  git commit --no-verify"
  exit 1
fi

echo "✅ server.py = $LINES lignes (seuil $THRESHOLD)"
exit 0
