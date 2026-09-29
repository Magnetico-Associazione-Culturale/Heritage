#!/usr/bin/env python3
"""Ottimizza i media dei comuni: immagini in WebP e audio in AAC (.m4a).

Uso (dalla radice del repo):
    python3 optimize_media.py                      # tutti i comuni
    python3 optimize_media.py "Comune di Niscemi"  # un solo comune
    python3 optimize_media.py --dry-run            # mostra cosa farebbe, senza toccare nulla

Lo esegue in automatico la GitHub Action "Ottimizza media" a ogni push che tocca media/.

Profili (vedi README, sezione "Media: formati e ottimizzazione"):
  - 360°   (format "360" nei JSON o cartella media/images/360/): WebP q88, lato lungo max 4096 px
            (è il massimo che l'app usa: i pixel in più verrebbero scartati sul telefono)
  - logo   (media/branding/logo*, o PNG con trasparenza): WebP q90, max 1024 px, trasparenza mantenuta
  - foto   (tutte le altre immagini): WebP q82, lato lungo max 2048 px
  - audio  (mp3, wav, m4a, aac, …): AAC mono 64 kbps in .m4a, adatto alla voce
  - media/qr/ non viene toccata (i QR restano PNG senza perdita).

Per ogni file convertito:
  - l'originale viene eliminato (resta nella cronologia git);
  - i path nei JSON del comune (anche traduzioni, chiavi comprese) e gli URL in catalog.json
    vengono aggiornati alla nuova estensione;
  - l'impronta del risultato finisce in <comune>/media/.optimized.json: i file già ottimizzati
    non vengono mai ricompressi (niente perdita di qualità a ogni passaggio).

Dipendenze: Pillow (pip install pillow; pillow-heif per le foto HEIC dell'iPhone) e, per
l'audio, ffmpeg. Su macOS senza ffmpeg si usa afconvert, già incluso nel sistema.
"""
import argparse
import datetime
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
from urllib.parse import quote

try:
    from PIL import Image, ImageCms, ImageOps
except ImportError:
    sys.exit("Serve Pillow: pip install pillow")

try:  # facoltativo: foto HEIC dell'iPhone
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIC = True
except ImportError:
    HEIC = False

Image.MAX_IMAGE_PIXELS = None  # i panorami originali superano il limite di sicurezza di Pillow

REPO_PREFIX = "https://raw.githubusercontent.com/Magnetico-Associazione-Culturale/Heritage/main/"
LOG_NAME = ".optimized.json"
# Cambia questo numero se cambi i profili: i file già registrati con una versione diversa
# NON vengono ricompressi (lo sarebbero da un file già compresso); vale per i nuovi caricamenti.
PROFILE_VERSION = 1

PROFILES = {
    "360": {"max_edge": 4096, "quality": 88},
    "logo": {"max_edge": 1024, "quality": 90},
    "foto": {"max_edge": 2048, "quality": 82},
}
MIN_SAVING = 0.9  # il WebP deve pesare almeno il 10% in meno dell'originale
AUDIO_BITRATE_K = 64
AUDIO_ADOPT_MAX_K = 96  # un .m4a già a questo bitrate o meno si tiene com'è

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".aif", ".aiff", ".flac", ".ogg", ".opus", ".caf"}
SKIP_DIRS = ("media/qr/",)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def kb(n):
    return f"{n / 1024:,.0f} KB" if n < 1024 * 1024 else f"{n / 1048576:,.1f} MB"


# ---- riferimenti nei JSON del comune ----

def comune_json_files(folder):
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != "media" and not d.startswith(".")]
        for name in files:
            if name.endswith(".json"):
                yield os.path.join(root, name)


def panorama_paths(folder):
    """Path delle immagini dichiarate con format "360" in qualsiasi JSON del comune."""
    found = set()

    def walk(node):
        if isinstance(node, dict):
            if node.get("format") == "360" and isinstance(node.get("path"), str):
                found.add(node["path"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for path in comune_json_files(folder):
        try:
            with open(path, encoding="utf-8") as f:
                walk(json.load(f))
        except (OSError, ValueError):
            pass  # JSON rotto: lo segnala il validatore
    return found


def replace_references(folder, old_rel, new_rel, dry_run):
    """Sostituisce il path (come stringa JSON, valore o chiave) nei JSON del comune e l'URL nel catalogo."""
    changed = []
    targets = [(p, f'"{old_rel}"', f'"{new_rel}"') for p in comune_json_files(folder)]
    base = REPO_PREFIX + quote(os.path.basename(folder)) + "/"
    targets.append(("catalog.json", f'"{base}{old_rel}"', f'"{base}{new_rel}"'))
    for path, old, new in targets:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if old not in text:
            continue
        changed.append(path)
        if not dry_run:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text.replace(old, new))
    return changed


def bump_content_version(folder):
    """Nuovo content_version nel manifest: senza, l'app terrebbe in cache i JSON con i vecchi path."""
    manifest = os.path.join(folder, "manifest.json")
    with open(manifest, encoding="utf-8") as f:
        text = f.read()
    current = json.loads(text).get("content_version", "")
    today = datetime.date.today().isoformat()
    new = today
    if current.split(".")[0] == today:
        suffix = current.split(".")[1] if "." in current else "1"
        new = f"{today}.{int(suffix) + 1 if suffix.isdigit() else 2}"
    old = f'"content_version": {json.dumps(current, ensure_ascii=False)}'
    if old not in text:
        raise RuntimeError(f"{manifest}: content_version non trovato, aggiornalo a mano")
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(text.replace(old, f'"content_version": "{new}"', 1))
    return current, new


# ---- immagini ----

def image_profile(rel, panoramas, image):
    if rel in panoramas or "/360/" in rel:
        return "360"
    name = os.path.basename(rel).lower()
    if rel.startswith("media/branding/") and name.startswith("logo"):
        return "logo"
    if has_transparency(image):
        return "logo"
    return "foto"


def has_transparency(image):
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        alpha = image.convert("RGBA").getchannel("A")
        return alpha.getextrema()[0] < 255
    return False


def to_srgb(image):
    """Converte in sRGB le foto con profilo colore (es. Display P3 dell'iPhone)."""
    icc = image.info.get("icc_profile")
    if not icc:
        return image
    try:
        src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        dst = ImageCms.createProfile("sRGB")
        mode = "RGBA" if image.mode in ("RGBA", "LA", "PA") else "RGB"
        return ImageCms.profileToProfile(image.convert(mode), src, dst, outputMode=mode)
    except (ImageCms.PyCMSError, OSError, ValueError):
        return image


def encode_image(src, dst, profile_name, image):
    profile = PROFILES[profile_name]
    image = ImageOps.exif_transpose(image)  # rispetta la rotazione della fotocamera
    keep_alpha = has_transparency(image)
    image = to_srgb(image)
    image = image.convert("RGBA" if keep_alpha else "RGB")
    w, h = image.size
    edge = profile["max_edge"]
    if max(w, h) > edge:
        scale = edge / max(w, h)
        image = image.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    # Nessun metadato copiato: niente EXIF né GPS (privacy) nel file pubblicato.
    image.save(dst, "WEBP", quality=profile["quality"], method=6)
    return image.size


# ---- audio ----

def audio_info(path):
    """(bitrate in kbps, canali) se ffprobe è disponibile, altrimenti (None, None)."""
    if not shutil.which("ffprobe"):
        return None, None
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
             "stream=bit_rate,channels", "-of", "json", path],
            capture_output=True, text=True, check=True,
        ).stdout
        stream = json.loads(out)["streams"][0]
        rate = int(stream.get("bit_rate", 0)) // 1000 or None
        return rate, stream.get("channels")
    except (subprocess.CalledProcessError, ValueError, KeyError, IndexError):
        return None, None


def encode_audio(src, dst):
    if shutil.which("ffmpeg"):
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-map_metadata", "-1",
             "-ac", "1", "-c:a", "aac", "-b:a", f"{AUDIO_BITRATE_K}k",
             # moov in testa: l'audio parte subito in streaming, senza scaricarlo tutto
             "-movflags", "+faststart", dst],
            check=True,
        )
        return "ffmpeg"
    if shutil.which("afconvert"):  # macOS
        subprocess.run(
            ["afconvert", "-f", "m4af", "-d", "aac", "-b", str(AUDIO_BITRATE_K * 1000),
             "-c", "1", src, dst],
            check=True,
        )
        return "afconvert"
    raise RuntimeError("serve ffmpeg (o afconvert su macOS) per convertire l'audio")


# ---- comune ----

def optimize_comune(folder, dry_run):
    media = os.path.join(folder, "media")
    if not os.path.isdir(media):
        return []
    log_path = os.path.join(media, LOG_NAME)
    log = {}
    if os.path.isfile(log_path):
        with open(log_path, encoding="utf-8") as f:
            log = json.load(f)
    panoramas = panorama_paths(folder)
    results = []
    renamed = False

    for root, dirs, files in os.walk(media):
        dirs.sort()
        for name in sorted(files):
            if name.startswith("."):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, folder).replace(os.sep, "/")
            ext = os.path.splitext(name)[1].lower()
            if rel.startswith(SKIP_DIRS) or ext not in IMAGE_EXT | AUDIO_EXT:
                continue
            digest = sha256(path)
            if log.get(rel, {}).get("sha256") == digest:
                continue  # già ottimizzato: non si ricomprime mai

            size = os.path.getsize(path)
            is_audio = ext in AUDIO_EXT
            new_rel = os.path.splitext(rel)[0] + (".m4a" if is_audio else ".webp")
            new_path = os.path.join(folder, new_rel)
            entry = {"kind": "audio" if is_audio else None, "source": rel, "source_bytes": size,
                     "profile_version": PROFILE_VERSION}

            if new_rel != rel and os.path.exists(new_path):
                results.append((rel, "ERRORE", f"esiste già {new_rel}: rinomina uno dei due", size, size))
                continue

            try:
                if is_audio:
                    rate, _ = audio_info(path)
                    if ext == ".m4a" and (rate is None or rate <= AUDIO_ADOPT_MAX_K):
                        action, out_size = "adottato", size  # già nel formato giusto
                    elif dry_run:
                        action, out_size = "audio → m4a", None
                    else:
                        tmp = new_path + ".tmp.m4a"
                        entry["encoder"] = encode_audio(path, tmp)
                        os.replace(tmp, new_path)
                        action, out_size = f"audio {AUDIO_BITRATE_K} kbps mono", os.path.getsize(new_path)
                else:
                    with Image.open(path) as image:
                        image.load()
                        profile = image_profile(rel, panoramas, image)
                        entry["kind"] = profile
                        limit = PROFILES[profile]["max_edge"]
                        if ext == ".webp" and max(image.size) <= limit:
                            action, out_size = "adottato", size  # già WebP nei limiti
                        elif dry_run:
                            action, out_size = f"{profile} → webp", None
                        else:
                            tmp = new_path + ".tmp.webp"
                            w, h = encode_image(path, tmp, profile, image)
                            # Sotto il 10% di risparmio non vale una seconda compressione: si tiene
                            # l'originale (JPEG e PNG l'app li legge comunque).
                            if new_rel == rel or os.path.getsize(tmp) < size * MIN_SAVING:
                                os.replace(tmp, new_path)
                                action, out_size = f"{profile} {w}×{h}", os.path.getsize(new_path)
                            else:
                                os.remove(tmp)
                                new_rel, new_path = rel, path
                                action, out_size = "tenuto (già leggero)", size
            except Exception as exc:  # un file rotto non deve fermare gli altri
                for leftover in (new_path + ".tmp.m4a", new_path + ".tmp.webp"):
                    if os.path.exists(leftover):
                        os.remove(leftover)
                results.append((rel, "ERRORE", str(exc), size, size))
                continue

            if not dry_run:
                if new_rel != rel:
                    os.remove(path)
                    replace_references(folder, rel, new_rel, dry_run=False)
                    log.pop(rel, None)
                    renamed = True
                entry["bytes"] = os.path.getsize(new_path)
                entry["sha256"] = sha256(new_path)
                log[new_rel] = entry
            refs = replace_references(folder, rel, new_rel, dry_run=True) if dry_run and new_rel != rel else []
            note = f" (aggiorna {len(refs)} file JSON)" if refs else ""
            results.append((rel, action + note, new_rel, size, out_size))

    if not dry_run and results:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(log.items())), f, ensure_ascii=False, indent=2)
            f.write("\n")
    if renamed:
        old, new = bump_content_version(folder)
        results.append(("manifest.json", "content_version", f"{old} → {new}", 0, 0))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("comuni", nargs="*", help='cartelle da ottimizzare (default: tutte le "Comune di …")')
    parser.add_argument("--dry-run", action="store_true", help="mostra cosa farebbe, senza modificare file")
    args = parser.parse_args()

    folders = args.comuni or sorted(d for d in os.listdir(".") if d.startswith("Comune di ") and os.path.isdir(d))
    if not HEIC:
        print("(pillow-heif non installato: le foto .heic verranno segnalate come errore)")

    total_in = total_out = 0
    errors = 0
    for folder in folders:
        folder = folder.rstrip("/")
        results = optimize_comune(folder, args.dry_run)
        if not results:
            print(f"{folder}: nulla da ottimizzare")
            continue
        print(f"\n{folder}")
        for rel, action, detail, before, after in results:
            if action == "content_version":
                print(f"  manifest.json: content_version {detail} (l'app ricarica i nuovi path)")
                continue
            if action == "ERRORE":
                errors += 1
                print(f"  ERRORE  {rel}: {detail}")
                continue
            total_in += before
            if after is None:
                print(f"  {rel}: {action} ({kb(before)})")
                continue
            total_out += after
            saved = f"-{100 * (1 - after / before):.0f}%" if before else ""
            target = f" → {os.path.basename(detail)}" if detail != rel else ""
            print(f"  {rel}{target}: {action}, {kb(before)} → {kb(after)} {saved}")

    if total_out:
        print(f"\nTotale: {kb(total_in)} → {kb(total_out)} (-{100 * (1 - total_out / total_in):.0f}%)")
    if errors:
        print(f"{errors} errori")
        sys.exit(1)


if __name__ == "__main__":
    main()
