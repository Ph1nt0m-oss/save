"""
iter110 — Site Issues collector
Endpoints créa+admin uniquement pour gérer les bugs/erreurs du site.
"""
from typing import Optional, List
from pydantic import BaseModel


# Imports gérés par server.py (api_router, db, etc.) — ce fichier est concatené dans server.py
# en attendant le refactoring route. Pour simplicité, on l'inline.
