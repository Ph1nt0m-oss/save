#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Télécharge un flux RSS/Atom et imprime les titres.

Dépendance :
  pip install requests

Exemple :
  python feed.py "https://www.france24.com/fr/rss"
"""

import sys
import requests
import xml.etree.ElementTree as ET


def telecharger(url: str) -> bytes:
    en_tetes = {
        "User-Agent": "LecteurRSS/1.0",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    }
    reponse = requests.get(url, headers=en_tetes, timeout=20)
    reponse.raise_for_status()
    return reponse.content


def imprimer_titres(xml_bytes: bytes) -> None:
    racine = ET.fromstring(xml_bytes)
    tag_sans_ns = racine.tag.split("}")[-1].lower()

    # RSS 2.0 : <rss><channel><item><title>
    channel = racine.find("channel")
    if tag_sans_ns == "rss" or channel is not None:
        channel = channel if channel is not None else racine
        for item in channel.findall("item"):
            titre = (item.findtext("title") or "").strip()
            if titre:
                print(titre)
        return

    # Atom : <feed xmlns="http://www.w3.org/2005/Atom"><entry><title>
    if tag_sans_ns == "feed":
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entrees = racine.findall("atom:entry", ns) or racine.findall("entry")
        for entree in entrees:
            titre = (
                entree.findtext("atom:title", default="", namespaces=ns)
                or entree.findtext("title")
                or ""
            ).strip()
            if titre:
                print(titre)
        return

    raise ValueError("Format de flux non reconnu (ni RSS 2.0 ni Atom).")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage : python feed.py <url_du_flux>", file=sys.stderr)
        return 2

    url = sys.argv[1]
    try:
        contenu = telecharger(url)
        imprimer_titres(contenu)
        return 0
    except requests.exceptions.RequestException as e:
        print(f"Erreur réseau : {e}", file=sys.stderr)
        return 3
    except ET.ParseError as e:
        print(f"Erreur XML (flux invalide) : {e}", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
