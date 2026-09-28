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

# ---- informativa privacy (facoltativa ma consigliata: gli store la richiedono) ----
import re

privacy = catalog.get("privacy")
if privacy is None:
    warnings.append("privacy: blocco assente, l'app non potrà mostrare l'informativa")
elif not isinstance(privacy, dict):
    errors.append("privacy: deve essere un oggetto")
else:
    files = privacy.get("files")
    default = privacy.get("default_language")
    if not isinstance(files, dict) or not files:
        errors.append("privacy.files: deve elencare almeno una lingua ({ \"it\": URL, ... })")
        files = {}
    if default not in files:
        errors.append(f"privacy.default_language '{default}' non è tra le lingue di privacy.files")
    section_counts = {}
    for lang, url in files.items():
        where = f"privacy.files.{lang}"
        if not isinstance(url, str) or not url.startswith("https://"):
            errors.append(f"{where}: deve essere un URL https")
            continue
        if not url.startswith(REPO_PREFIX):
            warnings.append(f"{where}: file ospitato fuori da questo repo, non verificato")
            continue
        local = unquote(url[len(REPO_PREFIX):])
        if not os.path.isfile(local):
            errors.append(f"{where}: file non trovato in questo repo ({local})")
            continue
        try:
            with open(local, encoding="utf-8") as pf:
                doc = json.load(pf)
        except ValueError as exc:
            errors.append(f"{local}: JSON non valido ({exc})")
            continue
        if doc.get("language") != lang:
            errors.append(f"{local}: 'language' è '{doc.get('language')}', atteso '{lang}'")
        for field in ("title", "summary"):
            if not isinstance(doc.get(field), str) or not doc[field].strip():
                errors.append(f"{local}: '{field}' obbligatorio (testo non vuoto)")
        if not isinstance(doc.get("updated"), str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", doc["updated"]):
            errors.append(f"{local}: 'updated' deve essere una data AAAA-MM-GG")
        sections = doc.get("sections")
        if not isinstance(sections, list) or not sections:
            errors.append(f"{local}: 'sections' deve essere un array non vuoto")
            continue
        for i, section in enumerate(sections):
            if not isinstance(section, dict) or not all(
                isinstance(section.get(k), str) and section[k].strip() for k in ("title", "body")
            ):
                errors.append(f"{local}: sections[{i}] deve avere 'title' e 'body' non vuoti")
        section_counts[lang] = (len(sections), doc.get("updated"))
    if len({count for count, _ in section_counts.values()}) > 1:
        warnings.append(f"privacy: numero di sezioni diverso tra le lingue {section_counts}: verifica le traduzioni")
    if len({updated for _, updated in section_counts.values()}) > 1:
        warnings.append(f"privacy: date 'updated' diverse tra le lingue {section_counts}: verifica le traduzioni")

for w in warnings:
    print(f"AVVISO  {w}")
for e in errors:
    print(f"ERRORE  {e}")
print(f"{len(comuni)} comuni, {len(errors)} errori, {len(warnings)} avvisi")
sys.exit(1 if errors else 0)
