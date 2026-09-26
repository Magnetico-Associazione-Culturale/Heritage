#!/usr/bin/env python3
"""Valida catalog.json (radice del repo): da eseguire nella radice.

Controlla che ogni voce abbia i campi obbligatori, che gli id siano unici, che
manifest_url punti a una cartella comune esistente in questo repo con lo stesso
comune_id e che le coordinate siano plausibili.
"""
import json
import os
import sys
from urllib.parse import unquote

REPO_PREFIX = "https://raw.githubusercontent.com/Magnetico-Associazione-Culturale/Heritage/main/"
REQUIRED = ["id", "name", "manifest_url", "center", "radius_km", "status"]
STATUSES = {"published", "preview"}

errors = []
warnings = []

with open("catalog.json", encoding="utf-8") as f:
    catalog = json.load(f)

comuni = catalog.get("comuni")
if not isinstance(comuni, list) or not comuni:
    errors.append("'comuni' deve essere un array non vuoto")
    comuni = []

seen = set()
for index, entry in enumerate(comuni):
    label = entry.get("id") or f"voce {index}"
    for field in REQUIRED:
        if field not in entry:
            errors.append(f"{label}: campo obbligatorio mancante '{field}'")

    comune_id = entry.get("id", "")
    if comune_id in seen:
        errors.append(f"{label}: id duplicato")
    seen.add(comune_id)
    if comune_id and (not comune_id.replace("-", "").isalnum() or comune_id != comune_id.lower()):
        errors.append(f"{label}: id deve essere minuscolo, lettere/numeri/trattini")

    if entry.get("status") not in STATUSES:
        errors.append(f"{label}: status deve essere uno di {sorted(STATUSES)}")

    center = entry.get("center") or {}
    lat, lon = center.get("lat"), center.get("lon")
    if not isinstance(lat, (int, float)) or not -90 <= lat <= 90:
        errors.append(f"{label}: center.lat non valido")
    if not isinstance(lon, (int, float)) or not -180 <= lon <= 180:
        errors.append(f"{label}: center.lon non valido")

    radius = entry.get("radius_km")
    if not isinstance(radius, (int, float)) or radius <= 0:
        errors.append(f"{label}: radius_km deve essere un numero positivo")

    url = entry.get("manifest_url", "")
    if not url.startswith("https://"):
        errors.append(f"{label}: manifest_url deve essere un URL https")
    elif url.startswith(REPO_PREFIX):
        local = unquote(url[len(REPO_PREFIX):])
        if not os.path.isfile(local):
            errors.append(f"{label}: manifest non trovato in questo repo ({local})")
        else:
            with open(local, encoding="utf-8") as mf:
                manifest_id = json.load(mf).get("comune_id")
            if manifest_id != comune_id:
                errors.append(f"{label}: comune_id del manifest è '{manifest_id}', atteso '{comune_id}'")
    else:
        warnings.append(f"{label}: manifest ospitato fuori da questo repo, non verificato")

    for field in ("logo_url", "cover_url"):
        value = entry.get(field)
        if value is not None and not str(value).startswith("https://"):
            errors.append(f"{label}: {field} deve essere un URL https")

for w in warnings:
    print(f"AVVISO  {w}")
for e in errors:
    print(f"ERRORE  {e}")
print(f"{len(comuni)} comuni, {len(errors)} errori, {len(warnings)} avvisi")
sys.exit(1 if errors else 0)
