#!/usr/bin/env python3
"""
Validatore contenuti Heritage.
Uso:  python3 validate.py
Esegui dalla radice del repo del comune. Verifica:
  - tutti i JSON sono validi
  - ogni monument_id referenziato in itinerari/quiz esiste
  - ogni path di media puntato dai JSON esiste su disco (e avvisa se non è ancora ottimizzato)
  - i campi obbligatori dei monumenti sono presenti
  - le attività (businesses.json, se elencato nel manifest) hanno categoria esistente,
    near_monuments esistenti, orari nel formato corretto e immagini presenti
  - le traduzioni (i18n/<lingua>/) puntano a id esistenti, contengono solo campi
    traducibili e segnala i testi non ancora tradotti
Esce con codice 1 se trova errori.
"""
import json
import os
import re
import sys

ERRORS = []
WARN = []


def load(name):
    try:
        with open(name, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        ERRORS.append(f"File mancante: {name}")
        return None
    except json.JSONDecodeError as e:
        ERRORS.append(f"JSON non valido in {name}: {e}")
        return None


OPTIMIZED_EXT = (".webp", ".m4a")
# JPEG/PNG tenuti apposta da optimize_media.py (risparmio sotto il 10%) sono nel suo registro.
OPTIMIZED_LOG = "media/.optimized.json"


def optimized_paths():
    try:
        with open(OPTIMIZED_LOG, encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


OPTIMIZED = optimized_paths()


def check_path(path, where):
    if not path:
        return
    if not os.path.exists(path):
        ERRORS.append(f"Media mancante ({where}): {path}")
    elif not path.lower().endswith(OPTIMIZED_EXT) and path not in OPTIMIZED and not path.startswith("media/qr/"):
        WARN.append(f"Media non ottimizzato ({where}): {path}: lo converte l'Action "
                    f"'Ottimizza media' al push (o python3 optimize_media.py nella radice)")


def tr_obj(lang, where, tr, allowed):
    if not isinstance(tr, dict):
        ERRORS.append(f"[{lang}] {where}: atteso un oggetto")
        return {}
    extra = sorted(set(tr) - set(allowed))
    if extra:
        ERRORS.append(f"[{lang}] {where}: campi non traducibili: {', '.join(extra)}")
    return tr


def tr_keyed(lang, where, base_keys, tr):
    if not isinstance(tr, dict):
        ERRORS.append(f"[{lang}] {where}: atteso un oggetto con chiave id")
        return {}
    for k in tr:
        if k not in base_keys:
            ERRORS.append(f"[{lang}] {where}: chiave inesistente nei file base: {k}")
    return tr


def tr_missing(base, tr, fields):
    return [f for f in fields if base.get(f) and not tr.get(f)]


def report_missing(lang, where, missing):
    if missing:
        WARN.append(f"[{lang}] {where}: non tradotti: {', '.join(missing)}")


MON_TEXT = ("name", "short_description", "description", "address", "tags")


def check_monuments_tr(lang, monuments, tr):
    tr = tr_keyed(lang, "monuments", {m.get("id") for m in monuments}, tr)
    for m in monuments:
        mid = m.get("id")
        where = f"monumento '{mid}'"
        if mid not in tr:
            WARN.append(f"[{lang}] {where}: non tradotto")
            continue
        t = tr_obj(lang, where, tr[mid], MON_TEXT + ("audio", "images", "history"))
        missing = tr_missing(m, t, MON_TEXT)
        if m.get("audio") and not t.get("audio"):
            missing.append(f"audio (resta in '{m['audio'].get('language', '?')}')")
        if t.get("audio"):
            check_path(t["audio"].get("path"), f"audio {lang} {mid}")
            if t["audio"].get("language") != lang:
                WARN.append(f"[{lang}] {where}: audio.language dovrebbe essere '{lang}'")
        imgs = {i.get("path"): i for i in m.get("images", [])}
        t_imgs = tr_keyed(lang, f"{where} images", imgs, t.get("images", {}))
        for path, img in imgs.items():
            ti = tr_obj(lang, f"{where} immagine {path}", t_imgs.get(path, {}), ("title", "alt"))
            missing += [f"images[{path}].{f}" for f in tr_missing(img, ti, ("title", "alt"))]
        hist = m.get("history") or []
        t_hist = t.get("history", [])
        if not isinstance(t_hist, list) or len(t_hist) > len(hist):
            ERRORS.append(f"[{lang}] {where}: 'history' deve essere un array di al massimo "
                          f"{len(hist)} voci, nello stesso ordine dei file base")
            t_hist = []
        for i, h in enumerate(hist):
            th = tr_obj(lang, f"{where} history[{i}]", t_hist[i] if i < len(t_hist) else {},
                        ("title", "description"))
            missing += [f"history[{i}].{f}" for f in tr_missing(h, th, ("title", "description"))]
        report_missing(lang, where, missing)


def check_itineraries_tr(lang, itineraries, tr):
    tr = tr_keyed(lang, "itineraries", {i.get("id") for i in itineraries}, tr)
    for it in itineraries:
        iid = it.get("id")
        where = f"itinerario '{iid}'"
        if iid not in tr:
            WARN.append(f"[{lang}] {where}: non tradotto")
            continue
        t = tr_obj(lang, where, tr[iid], ("name", "short_name", "description", "stops"))
        missing = tr_missing(it, t, ("name", "short_name", "description"))
        stops = {s.get("monument_id"): s for s in it.get("stops", [])}
        t_stops = tr_keyed(lang, f"{where} stops", stops, t.get("stops", {}))
        for ref, s in stops.items():
            ts = tr_obj(lang, f"{where} tappa {ref}", t_stops.get(ref, {}), ("note",))
            missing += [f"stops[{ref}].note" for _ in tr_missing(s, ts, ("note",))]
        report_missing(lang, where, missing)


def check_quizzes_tr(lang, quizzes, tr):
    tr = tr_keyed(lang, "quizzes", {q.get("id") for q in quizzes}, tr)
    for quiz in quizzes:
        qzid = quiz.get("id")
        where = f"quiz '{qzid}'"
        if qzid not in tr:
            WARN.append(f"[{lang}] {where}: non tradotto")
            continue
        t = tr_obj(lang, where, tr[qzid], ("title", "description", "questions"))
        missing = tr_missing(quiz, t, ("title", "description"))
        questions = {q.get("id"): q for q in quiz.get("questions", [])}
        t_qs = tr_keyed(lang, f"{where} questions", questions, t.get("questions", {}))
        for qid, q in questions.items():
            tq = tr_obj(lang, f"{where} domanda {qid}", t_qs.get(qid, {}),
                        ("text", "options", "explanation"))
            missing += [f"{qid}.{f}" for f in tr_missing(q, tq, ("text", "explanation"))]
            opts = {o.get("id"): o for o in q.get("options", [])}
            t_opts = tr_keyed(lang, f"{where} domanda {qid} options", opts, tq.get("options", {}))
            missing += [f"{qid}.options.{oid}" for oid, o in opts.items()
                        if o.get("text") and not t_opts.get(oid)]
        report_missing(lang, where, missing)


BUS_TEXT = ("name", "short_description", "description", "hours_note", "tags")


def check_businesses_tr(lang, data, tr):
    t = tr_obj(lang, "businesses", tr, ("categories", "businesses"))
    categories = {c.get("id"): c for c in data.get("categories", [])}
    t_cats = tr_keyed(lang, "businesses categories", categories, t.get("categories", {}))
    for cid, c in categories.items():
        tc = tr_obj(lang, f"categoria '{cid}'", t_cats.get(cid, {}), ("label",))
        report_missing(lang, f"categoria '{cid}'", tr_missing(c, tc, ("label",)))
    businesses = {b.get("id"): b for b in data.get("businesses", [])}
    t_bus = tr_keyed(lang, "businesses", businesses, t.get("businesses", {}))
    for bid, b in businesses.items():
        where = f"attività '{bid}'"
        if bid not in t_bus:
            WARN.append(f"[{lang}] {where}: non tradotta")
            continue
        tb = tr_obj(lang, where, t_bus[bid], BUS_TEXT + ("images",))
        missing = [f for f in tr_missing(b, tb, BUS_TEXT) if f != "name"]  # i nomi propri restano
        imgs = {i.get("path"): i for i in b.get("images") or []}
        t_imgs = tr_keyed(lang, f"{where} images", imgs, tb.get("images", {}))
        for path, img in imgs.items():
            ti = tr_obj(lang, f"{where} immagine {path}", t_imgs.get(path, {}), ("alt",))
            missing += [f"images[{path}].alt" for _ in tr_missing(img, ti, ("alt",))]
        report_missing(lang, where, missing)


def check_config_tr(lang, config, tr):
    t = tr_obj(lang, "config", tr, ("comune",))
    comune = config.get("comune", {})
    tc = tr_obj(lang, "config comune", t.get("comune", {}),
                ("name", "short_description", "description", "patron_saint"))
    report_missing(lang, "config", tr_missing(comune, tc, ("short_description", "description")))


def check_translations(manifest, base):
    default = manifest.get("default_language")
    langs = manifest.get("available_languages") or []
    translations = manifest.get("translations") or {}
    if default not in langs:
        ERRORS.append(f"manifest.json: default_language '{default}' non e' in available_languages")
    for lang in translations:
        if lang not in langs or lang == default:
            WARN.append(f"manifest.json: 'translations.{lang}' ignorata (lingua predefinita "
                        f"o assente da available_languages)")
    checks = {
        "config": check_config_tr,
        "monuments": check_monuments_tr,
        "itineraries": check_itineraries_tr,
        "quizzes": check_quizzes_tr,
        "businesses": check_businesses_tr,
    }
    # Le attività sono facoltative: si controllano solo se il comune le ha.
    checks = {key: check for key, check in checks.items() if key in base}
    for lang in langs:
        if lang == default:
            continue
        files = translations.get(lang)
        if not isinstance(files, dict):
            ERRORS.append(f"manifest.json: lingua '{lang}' senza voce in 'translations'")
            continue
        for key, check in checks.items():
            if not files.get(key):
                WARN.append(f"[{lang}] manifest.json: manca translations.{lang}.{key} "
                            f"(contenuti mostrati in '{default}')")
                continue
            tr = load(files[key])
            if tr is not None:
                check(lang, base[key], tr)


DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
TIME_RE = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
CONTACT_FIELDS = ("phone", "whatsapp", "email", "website", "instagram", "booking_url")
BUS_FIELDS = {"id", "name", "category", "subcategory", "short_description", "description", "lat", "lon",
              "address", "contacts", "opening_hours", "hours_note", "price_range", "tags", "languages",
              "accessible", "images", "near_monuments", "active", "updated_at"}


def check_businesses(data, monument_ids):
    """businesses.json: { categories: [...], businesses: [...] }."""
    if not isinstance(data, dict):
        ERRORS.append("businesses.json: atteso un oggetto { categories, businesses }")
        return
    categories = data.get("categories")
    businesses = data.get("businesses")
    if not isinstance(categories, list) or not isinstance(businesses, list):
        ERRORS.append("businesses.json: 'categories' e 'businesses' devono essere array")
        return

    cat_ids = set()
    for c in categories:
        cid = c.get("id")
        if not cid or not c.get("label"):
            ERRORS.append(f"Categoria senza id o label: {c}")
            continue
        if cid in cat_ids:
            ERRORS.append(f"Categoria duplicata: {cid}")
        cat_ids.add(cid)
        if not c.get("group"):
            WARN.append(f"Categoria '{cid}': manca 'group' (vivi / servizi), l'app usa 'vivi'")
        elif c["group"] not in ("vivi", "servizi"):
            WARN.append(f"Categoria '{cid}': group '{c['group']}' non tradotto nell'app (vivi / servizi)")
        if not c.get("icon"):
            WARN.append(f"Categoria '{cid}': manca 'icon' (nome icona lucide, es. utensils)")

    bus_ids = set()
    for b in businesses:
        bid = b.get("id")
        if not bid:
            ERRORS.append(f"Attività senza id: {b.get('name', '???')}")
            continue
        where = f"Attività '{bid}'"
        if bid in bus_ids:
            ERRORS.append(f"{where}: id duplicato")
        bus_ids.add(bid)
        extra = sorted(set(b) - BUS_FIELDS)
        if extra:
            WARN.append(f"{where}: campi sconosciuti (ignorati dall'app): {', '.join(extra)}")
        if not b.get("name"):
            ERRORS.append(f"{where}: manca 'name'")
        if b.get("category") not in cat_ids:
            ERRORS.append(f"{where}: category inesistente: {b.get('category')}")
        for req in ("short_description", "address"):
            if not b.get(req):
                WARN.append(f"{where}: campo consigliato mancante: {req}")
        lat, lon = b.get("lat"), b.get("lon")
        if (lat is None) != (lon is None) or any(v is not None and not isinstance(v, (int, float))
                                                 for v in (lat, lon)):
            ERRORS.append(f"{where}: lat/lon devono essere entrambi numeri o entrambi null")
        elif lat is None:
            WARN.append(f"{where}: senza coordinate (niente mappa, distanza e 'Apri in mappe')")
        price = b.get("price_range")
        if price is not None and price not in (1, 2, 3):
            ERRORS.append(f"{where}: price_range deve essere 1, 2, 3 o null: {price}")
        contacts = b.get("contacts") or {}
        if not isinstance(contacts, dict):
            ERRORS.append(f"{where}: 'contacts' deve essere un oggetto")
            contacts = {}
        for key in sorted(set(contacts) - set(CONTACT_FIELDS)):
            WARN.append(f"{where}: contatto sconosciuto (ignorato): {key}")
        for key in ("website", "booking_url"):
            url = contacts.get(key)
            if url and not str(url).startswith("https://"):
                ERRORS.append(f"{where}: contacts.{key} deve iniziare con https://: {url}")
        email = contacts.get("email")
        if email and "@" not in email:
            ERRORS.append(f"{where}: contacts.email non valida: {email}")
        hours = b.get("opening_hours")
        if hours is None or hours == []:
            WARN.append(f"{where}: senza orari (nessun badge Aperto/Chiuso)")
        elif not isinstance(hours, list):
            ERRORS.append(f"{where}: 'opening_hours' deve essere un array")
        else:
            for i, slot in enumerate(hours):
                days = slot.get("days")
                if not isinstance(days, list) or not days or any(d not in DAYS for d in days):
                    ERRORS.append(f"{where}: opening_hours[{i}].days deve contenere solo "
                                  f"mon, tue, wed, thu, fri, sat, sun: {days}")
                for key in ("open", "close"):
                    value = slot.get(key)
                    if not isinstance(value, str) or not TIME_RE.fullmatch(value):
                        ERRORS.append(f"{where}: opening_hours[{i}].{key} deve essere HH:MM "
                                      f"(00:00-23:59): {value}")
        for ref in b.get("near_monuments") or []:
            if ref not in monument_ids:
                ERRORS.append(f"{where}: near_monuments inesistente: {ref}")
        images = b.get("images") or []
        if not images:
            WARN.append(f"{where}: senza immagini (in elenco compare un segnaposto)")
        for img in images:
            path = img.get("path")
            if not path:
                ERRORS.append(f"{where}: immagine senza path")
            else:
                check_path(path, f"attività {bid}")
        if b.get("active") is False:
            WARN.append(f"{where}: active = false (non mostrata nell'app)")


def main():
    manifest = load("manifest.json") or {}
    config = load("config.json") or {}
    monuments = load("monuments.json") or []
    itineraries = load("itineraries.json") or []
    quizzes = load("quizzes.json") or []
    businesses_file = (manifest.get("files") or {}).get("businesses")
    businesses = load(businesses_file) if businesses_file else None

    monument_ids = set()

    # Monumenti
    for m in monuments:
        mid = m.get("id")
        if not mid:
            ERRORS.append(f"Monumento senza id: {m.get('name', '???')}")
            continue
        if mid in monument_ids:
            ERRORS.append(f"id duplicato: {mid}")
        monument_ids.add(mid)
        for req in ("name", "category", "short_description", "address"):
            if not m.get(req):
                WARN.append(f"[{mid}] campo consigliato mancante: {req}")
        if m.get("audio"):
            check_path(m["audio"].get("path"), f"audio {mid}")
        for img in m.get("images", []):
            check_path(img.get("path"), f"immagine {mid}")

    # Itinerari
    colors = {}
    for it in itineraries:
        iid = it.get("id")
        if not it.get("short_name"):
            WARN.append(f"Itinerario '{iid}': manca 'short_name' (nome nel selettore)")
        color = it.get("color")
        if not color:
            WARN.append(f"Itinerario '{iid}': manca 'color' (colore sulla mappa)")
        elif not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            ERRORS.append(f"Itinerario '{iid}': 'color' deve essere nel formato #RRGGBB: {color}")
        elif color.upper() in colors:
            WARN.append(f"Itinerario '{iid}': stesso colore di '{colors[color.upper()]}' ({color})")
        else:
            colors[color.upper()] = iid
        for stop in it.get("stops", []):
            ref = stop.get("monument_id")
            if ref and ref not in monument_ids:
                ERRORS.append(f"Itinerario '{it.get('id')}': monument_id inesistente: {ref}")
        check_path(it.get("cover_image"), f"itinerario {it.get('id')}")
        if len(it.get("path") or []) < 2:
            WARN.append(f"Itinerario '{it.get('id')}': manca 'path' (linea retta tra le tappe). "
                        f"Esegui build_routes.py dalla radice del repo")
        for leg in it.get("legs") or []:
            if leg.get("distance_km") == 0:
                WARN.append(f"Itinerario '{it.get('id')}': {leg.get('from')} e {leg.get('to')} "
                            f"hanno le stesse coordinate")

    # Quiz
    for q in quizzes:
        ref = q.get("monument_id")
        if ref and ref not in monument_ids:
            ERRORS.append(f"Quiz '{q.get('id')}': monument_id inesistente: {ref}")
        for question in q.get("questions", []):
            check_path(question.get("image"), f"quiz {q.get('id')}")
            corrects = [o for o in question.get("options", []) if o.get("correct")]
            if len(corrects) != 1:
                WARN.append(f"Quiz '{q.get('id')}' domanda '{question.get('id')}': "
                            f"{len(corrects)} risposte corrette (atteso 1)")

    # Attività (facoltative: solo se il manifest elenca businesses)
    if businesses is not None:
        check_businesses(businesses, monument_ids)

    # Mappa: il config deve richiamare il file mappa globale condiviso
    if not config.get("map", {}).get("config_url"):
        WARN.append("config.json: manca 'map.config_url' (config mappa globale condivisa)")

    # Landing page unica (QR + condivisione)
    share_url = config.get("app", {}).get("share_url")
    if not share_url:
        WARN.append("config.json: manca 'app.share_url' (landing page per QR e condivisione)")
    elif not share_url.startswith("https://") or not share_url.endswith("/"):
        WARN.append(f"config.json: 'app.share_url' deve iniziare con https:// e terminare con /: {share_url}")

    base = {
        "config": config,
        "monuments": monuments,
        "itineraries": itineraries,
        "quizzes": quizzes,
    }
    if isinstance(businesses, dict):
        base["businesses"] = businesses
    check_translations(manifest, base)

    # Report
    for w in WARN:
        print("WARN:", w)
    for e in ERRORS:
        print("ERRORE:", e)

    if ERRORS:
        print(f"\n{len(ERRORS)} errori, {len(WARN)} avvisi. Build NON pronta.")
        sys.exit(1)
    n_bus = len(businesses.get("businesses", [])) if isinstance(businesses, dict) else 0
    print(f"\nTutto ok ({len(monument_ids)} monumenti, {n_bus} attività). {len(WARN)} avvisi.")


if __name__ == "__main__":
    main()
