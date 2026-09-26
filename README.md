# Heritage — Contenuti per comune

Questo repo contiene i contenuti dell'app turistica **Heritage**: un'**unica app** sugli
store dentro la quale l'utente sceglie il comune da visitare (da un elenco oppure in
automatico in base alla sua posizione). L'app ha 6 sezioni principali — **Home, Itinerario,
Tappe, Tour (360°), Quiz, Info** — e legge i contenuti da file JSON + media associati.
Aggiornando i contenuti, l'app si aggiorna da remoto senza ripubblicare sugli store.

Ogni comune ha la propria **sottocartella** `Comune di <Nome>/`, completa e autonoma, ed è
elencato nel **catalogo** `catalog.json` nella radice. Per aggiungere un comune si **clona**
una sottocartella esistente, se ne adattano i contenuti e lo si aggiunge al catalogo: l'app
lo mostra senza bisogno di una nuova pubblicazione.

---

## Struttura del repo

```
/
├── README.md                    # Questa guida
├── catalog.json                 # Catalogo dei comuni mostrati nell'app (punto d'ingresso)
├── validate_catalog.py          # Validatore del catalogo (eseguire nella radice)
├── map.config.json              # Config mappa globale condivisa (provider + chiave Carto)
│
├── Comune di Bugliano/          # Istanza comune (contenuti template di riferimento)
│   ├── manifest.json            # Punto d'ingresso: versione + elenco dei file
│   ├── config.json              # Info comune, branding (colori e logo), base_url media, share_url
│   ├── monuments.json           # Punti di interesse (POI) → sezioni Tappe / Tour 360°
│   ├── itineraries.json         # Itinerari turistici sulla mappa → sezione Itinerario
│   ├── quizzes.json             # Quiz → sezione Quiz
│   ├── validate.py              # Validatore contenuti (eseguire dentro la cartella)
│   ├── i18n/                    # Traduzioni (opzionali), una cartella per lingua
│   │   └── en/                  # Stessi nomi file, solo i testi, per id
│   └── media/                   # Tutti gli asset (relativi a media.base_url)
│       ├── images/
│       │   ├── flat/            # Foto standard
│       │   ├── 360/             # Immagini equirettangolari per tour 360°
│       │   └── itineraries/     # Copertine degli itinerari
│       ├── audio/
│       │   ├── it/              # Audioguide in italiano
│       │   └── en/              # Audioguide in inglese (se presenti)
│       └── branding/            # Logo e splash dell'app
│
└── Comune di Niscemi/           # Altra istanza (stessa struttura, contenuti propri)
    └── …
```

> **Ogni `Comune di <Nome>/` è autonoma e clonabile:** contiene tutti i JSON, i media e il
> validatore. L'app la raggiunge tramite il `manifest_url` indicato nel catalogo. Se un
> comune viene spostato su un altro host o repo, si aggiornano solo il suo `manifest_url`
> nel catalogo e il suo `media.base_url`.

> **Config mappa condivisa:** oltre alle cartelle comune esiste un file globale
> `map.config.json` (nella radice di questo repo) con provider e chiave della mappa Carto,
> letto da tutte le build. Ogni `config.json` lo richiama via `map.config_url`. Vedi
> *Mappa: configurazione globale condivisa*.

> **Landing page e QR:** la pagina "scarica l'app" di ogni comune **non** sta in questo
> repo ma nel repo dedicato `heritage-pages` (GitHub Pages). Ogni `config.json` la
> richiama via `app.share_url`. Vedi *Landing page e QR code*.

---

## Catalogo dei comuni (`catalog.json`)

L'app è unica: all'avvio scarica il catalogo da un URL fisso, impostato nella build:

```
https://raw.githubusercontent.com/Magnetico-Associazione-Culturale/Heritage/main/catalog.json
```

```json
{
  "schema_version": "1.0",
  "comuni": [
    {
      "id": "niscemi",
      "name": "Niscemi",
      "province": "CL",
      "region": "Sicilia",
      "manifest_url": "https://raw.githubusercontent.com/Magnetico-Associazione-Culturale/Heritage/main/Comune%20di%20Niscemi/manifest.json",
      "center": { "lat": 37.1469, "lon": 14.3897 },
      "radius_km": 10,
      "logo_url": "https://…/Comune%20di%20Niscemi/media/branding/logo.png",
      "cover_url": "https://…/Comune%20di%20Niscemi/media/branding/splash.jpg",
      "status": "published"
    }
  ]
}
```

| Campo | Tipo | Obbl. | Note |
|---|---|---|---|
| `id` | string | sì | Slug del comune: uguale a `comune_id` del suo `manifest.json`. Non cambiarlo mai: è salvato sui dispositivi come comune scelto ed è usato nei link diretti. |
| `name` | string | sì | Nome mostrato nell'elenco dei comuni. |
| `province`, `region` | string | no | Mostrati sotto il nome e usati dalla ricerca. |
| `manifest_url` | string | sì | URL assoluto (https) del `manifest.json` del comune. |
| `center` | `{lat, lon}` | sì | Centro del territorio comunale, per la scelta automatica in base alla posizione. |
| `radius_km` | number | sì | Raggio (km) attorno a `center` entro cui l'utente è considerato "nel comune". |
| `logo_url`, `cover_url` | string | no | URL assoluti di logo e immagine di copertina per l'elenco. |
| `status` | string | sì | `published` = visibile a tutti; `preview` = visibile solo nelle build interne (preview/development), per provare un comune prima di renderlo pubblico. |

**Comportamento dell'app:**

1. **Primo avvio:** mostra l'elenco dei comuni (con ricerca). Se l'utente concede la
   posizione e si trova entro `radius_km` da un `center`, il comune viene aperto in
   automatico.
2. **Avvii successivi:** riapre l'ultimo comune. Se la posizione è già autorizzata e
   l'utente si trova in un altro comune del catalogo, l'app passa a quello e lo segnala con
   un avviso (con la possibilità di tornare indietro). Se più comuni contengono la
   posizione, vince il centro più vicino.
3. **Cambio manuale:** sempre possibile dalla Home e dalla sezione Info.
4. **Offline:** il catalogo e i contenuti restano in cache; al primo avvio senza rete
   l'app mostra l'errore con "Riprova".

Per togliere un comune dall'app basta rimuoverlo dal catalogo (o riportarlo a `preview`):
chi lo aveva scelto torna all'elenco.

Prima di ogni push esegui, **nella radice**:

```
python3 validate_catalog.py
```

Controlla campi e id, che ogni `manifest_url` di questo repo esista e che il suo
`comune_id` coincida con l'`id` del catalogo. Lo lancia anche la GitHub Action.

---

## Regola d'oro: i path

`config.json` definisce **un solo** `media.base_url`. Ogni path di immagine o audio negli
altri file è **relativo** a quel base_url.

L'app costruisce l'URL completo così:

```
url_completo = config.media.base_url + path_relativo
```

Esempio: con `base_url = "https://raw.githubusercontent.com/Magnetico-Associazione-Culturale/Heritage/main/Comune%20di%20Bugliano/"`
e `path = "media/images/flat/chiesa-san-giovanni.jpg"`, l'app scarica
`https://raw.githubusercontent.com/Magnetico-Associazione-Culturale/Heritage/main/Comune%20di%20Bugliano/media/images/flat/chiesa-san-giovanni.jpg`.

Il `base_url` deve terminare con `/` e gli spazi nel nome della cartella vanno scritti come `%20`.

**Vantaggio:** per spostare l'hosting (es. da GitHub a un CDN) cambi *una sola riga* in
`config.json`. Non toccare mai gli altri file.

---

## Mappa: configurazione globale condivisa

La mappa usa i basemap **Carto** (stile *voyager*), che richiedono una **chiave**. La chiave
**non è contenuto del comune** ma infrastruttura a livello di app, uguale per tutti. Per
questo **non** sta nei singoli `config.json`, ma in **un unico file remoto condiviso** —
`map.config.json` nella radice di questo repo — che ogni build scarica all'avvio:

```
https://raw.githubusercontent.com/Magnetico-Associazione-Culturale/Heritage/main/map.config.json
```

```json
{
  "provider": "carto",
  "style": "voyager",
  "tile_url": "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key={key}",
  "api_key": "LA_CHIAVE_QUI",
  "attribution": "© OpenStreetMap contributors © CARTO",
  "min_zoom": 0,
  "max_zoom": 20
}
```

Ogni `config.json` di comune **richiama** questo file tramite `map.config_url` (l'URL è lo
stesso per tutti — è solo un puntatore, non la chiave). All'avvio l'app:

```
map_config      = fetch(config.map.config_url)          // file globale condiviso
tile_url_finale = map_config.tile_url
                    .replace("{key}", map_config.api_key) // poi {z}/{x}/{y} per ogni tile
```

**Vantaggio:** quando la chiave scade o cambia, si aggiorna **solo il campo `api_key` di
questo file** e la modifica si propaga a **tutti i comuni da remoto**, senza ripubblicare
sugli store e senza toccare nessuna sottocartella comune. Le cartelle `Comune di <Nome>/`
restano autonome: la chiave non è duplicata al loro interno.

> **Sicurezza:** la chiave viaggia nel traffico di rete dell'app, non è un segreto.
> Proteggila lato Carto (restrizioni per bundle-id/dominio, limiti di quota), non con la
> segretezza del file.

---

## Landing page e QR code

Per ora **non** si usa un QR per monumento: ogni comune ha **un solo QR** (da stampare su
cartellonistica, brochure, ecc.) che punta a una **landing page** con i pulsanti per
scaricare l'app **Heritage** da App Store e Google Play (gli stessi link per tutti i comuni).
La landing può anche offrire un pulsante "Apri nell'app" con il link diretto al comune:

```
heritage://comune/<id>        # es. heritage://comune/niscemi
```

che apre l'app già installata direttamente sul comune (`<id>` è quello del catalogo).

Le landing page sono servite da **GitHub Pages** sul repo dedicato
[`heritage-pages`](https://github.com/Magnetico-Associazione-Culturale/heritage-pages),
con una sottocartella per comune:

```
heritage-pages/
├── Niscemi/
│   └── index.html      → https://magnetico-associazione-culturale.github.io/heritage-pages/Niscemi/
└── <Nome>/
    └── index.html      → https://magnetico-associazione-culturale.github.io/heritage-pages/<Nome>/
```

**Convenzione URL:**

```
https://magnetico-associazione-culturale.github.io/heritage-pages/<Nome>/
```

- `<Nome>` è il nome del comune con l'**iniziale maiuscola** (es. `Niscemi`, `Bugliano`).
  GitHub Pages distingue maiuscole e minuscole: `niscemi/` **non** funziona.
- L'URL termina sempre con `/`.

L'URL è salvato in `config.json` → `app.share_url` ed è usato dal **pulsante "Condividi
l'app"**: l'app apre il foglio di condivisione nativo (WhatsApp, messaggi, email…) con
questo link, così chi lo riceve arriva alla landing con i pulsanti degli store. È anche
l'URL da codificare nel QR: un'unica fonte di verità per entrambi.

> **Il QR non va mai rigenerato:** punta a un URL stabile. Se cambiano i link agli store o
> la grafica, si aggiorna solo `index.html` nel repo `heritage-pages`. Se in futuro si
> torna ai QR per monumento, basterà aggiungere un campo per POI in `monuments.json`.

---

## manifest.json

| Campo | Tipo | Descrizione |
|---|---|---|
| `schema_version` | string | Versione della struttura JSON. Cambiala solo se cambi i campi. |
| `content_version` | string | Data/versione dei contenuti. Aggiornala a ogni modifica per invalidare la cache. |
| `comune_id` | string | Slug del comune (minuscolo, senza spazi). |
| `default_language` | string | Lingua predefinita (`it`): è la lingua dei file base. |
| `available_languages` | string[] | Lingue mostrate nel selettore dell'app. |
| `files` | object | Nomi dei file di contenuto (così l'app sa cosa caricare). |
| `translations` | object | *(da schema 1.1)* Per ogni lingua diversa dalla predefinita, i file di traduzione. Vedi *Traduzioni*. |

---

## config.json

Contiene le info del comune, il suo branding (colori e logo) e il `base_url` dei media.
`comune.map_center` + `default_zoom` definiscono dove **centrare** la mappa all'avvio.
`app.theme` contiene i colori e il logo: l'app li applica quando l'utente apre questo comune.
`app.share_url` è il link condiviso dal pulsante "Condividi l'app": punta alla landing page
"scarica l'app" del comune, la stessa del QR unico (vedi *Landing page e QR code*).
`map.config_url` **richiama** il file mappa globale condiviso: provider e chiave (Carto)
**non** stanno qui (vedi *Mappa: configurazione globale condivisa*).

---

## monuments.json

Array di POI. **Compatibile con la struttura attuale di Regalbuto** (lat/lon flat, audio,
images, history). Campi:

| Campo | Tipo | Obbl. | Note |
|---|---|---|---|
| `id` | string | sì | Slug univoco. Usato come riferimento da itinerari e quiz. |
| `name` | string | sì | Nome visualizzato. |
| `category` | string | sì | `chiesa`, `palazzo`, `civico`, `tecnologia`, `museo`, `monumento`, ... |
| `short_description` | string | sì | Una riga per la lista. |
| `description` | string | no | Testo lungo per la scheda di dettaglio. |
| `lat`, `lon` | number\|null | sì | Coordinate. `null` se sconosciute (il pin non viene mostrato). |
| `address` | string | sì | Indirizzo testuale. |
| `tags` | string[] | no | Per filtri/ricerca. |
| `audio` | object\|null | no | Audioguida (vedi sotto). `null` se assente. |
| `images` | object[] | sì | Vedi sotto. |
| `history` | object[] | no | Voci storiche con periodo e `agents`. |

### audio
```json
{
  "path": "media/audio/it/01_chiesa.mp3",
  "duration": 180,
  "language": "it",
  "title": "Audioguida - ...",
  "description": "..."
}
```

### images
```json
{
  "role": "thumbnail",      // opzionale; "thumbnail" = immagine principale in lista
  "format": "standard",     // "standard" = foto normale | "360" = tour panoramico
  "path": "media/images/flat/x.jpg",
  "title": "...",
  "alt": "..."              // testo alternativo per accessibilità
}
```

> **Tour 360°:** le immagini panoramiche stanno *dentro* l'array `images` del monumento con
> `format: "360"`. Devono essere equirettangolari (rapporto 2:1, es. 4096×2048). L'app le
> rileva dal campo `format` e le apre nel viewer panoramico.

---

## itineraries.json

Array di percorsi. Le tappe **non duplicano** i dati del monumento: lo referenziano con
`monument_id`.

| Campo | Note |
|---|---|
| `id`, `name`, `description` | Identificativi e testi. |
| `short_name` | Nome breve (es. `Fede e Natura`) per il selettore degli itinerari nell'app. |
| `color` | Colore esadecimale `#RRGGBB` della polilinea e dei marker dell'itinerario sulla mappa. Usa colori diversi per ogni itinerario dello stesso comune. |
| `difficulty` | `easy` / `medium` / `hard`. |
| `distance_km` | Distanza reale del percorso (generata da `build_routes.py`). |
| `duration_minutes` | Stima della durata complessiva, **visite incluse** (manuale). |
| `travel_mode` | `walking` / `driving` / `bicycling`. Determina il profilo di routing. |
| `cover_image` | Copertina (path relativo). |
| `stops` | Lista ordinata: `{ order, monument_id, note }`. |
| `path` | Lista di `{lat, lon}` che segue le strade reali, da disegnare come polilinea. **Generata** da `build_routes.py`. Se assente, l'app collega le tappe in linea retta. |
| `legs` | **Generata.** Un elemento per ogni tratto tra tappe consecutive: `{ from, to, distance_km, travel_minutes }`. Serve per mostrare "prossima tappa: 350 m, 5 min". |

### Tracciato stradale degli itinerari

Il percorso reale tra le tappe **non va disegnato a mano**: si calcola offline con OSRM
(dati OpenStreetMap, stessi della basemap Carto) e si salva nel JSON. L'app non deve
chiamare nessun servizio di routing a runtime: disegna `path` sopra i tile Carto.

```
python3 build_routes.py                       # tutti i comuni
python3 build_routes.py "Comune di Niscemi"   # un solo comune
```

Va rieseguito ogni volta che si cambiano le tappe di un itinerario o le coordinate di un
monumento. Lo script aggiorna `path`, `distance_km` e `legs`; non tocca `duration_minutes`.

**In automatico:** la GitHub Action `.github/workflows/build-routes.yml` lo esegue a ogni
push su `main` che modifica `itineraries.json` o `monuments.json`, poi lancia `validate.py`
su ogni comune e committa i percorsi aggiornati. Si può avviare anche a mano da
*Actions → Genera percorsi itinerari → Run workflow*. Dopo ogni push fai `git pull` prima
di modificare di nuovo, perché l'Action aggiunge un suo commit.

---

## quizzes.json

Array di quiz. `monument_id` può essere `null` (quiz generale) o l'id di un monumento
(quiz contestuale alla sua scheda).

```json
{
  "id": "quiz-generale",
  "title": "...",
  "monument_id": null,
  "questions": [
    {
      "id": "q1",
      "text": "...",
      "image": "media/images/flat/x.jpg",   // o null
      "options": [
        { "id": "a", "text": "...", "correct": true },
        { "id": "b", "text": "...", "correct": false }
      ],
      "explanation": "Mostrata dopo la risposta."
    }
  ]
}
```

---

## Traduzioni (selettore lingua)

I file base (`monuments.json`, ecc.) sono nella **lingua predefinita** e restano l'unica
fonte per coordinate, percorsi, id, media e risposte corrette. Per ogni altra lingua si
aggiungono in `i18n/<lingua>/` file con **solo i testi**, indicizzati per id, e li si
registra nel manifest:

```json
"default_language": "it",
"available_languages": ["it", "en"],
"translations": {
  "en": {
    "config": "i18n/en/config.json",
    "monuments": "i18n/en/monuments.json",
    "itineraries": "i18n/en/itineraries.json",
    "quizzes": "i18n/en/quizzes.json"
  }
}
```

### Formato

Ogni file di traduzione è un **oggetto** (non un array) con chiave = `id` dell'elemento base.

| File | Campi traducibili |
|---|---|
| `config` | `comune.{name, short_description, description, patron_saint}` |
| `monuments` | `name`, `short_description`, `description`, `address`, `tags`, `audio`, `images`, `history` |
| `itineraries` | `name`, `short_name`, `description`, `stops` |
| `quizzes` | `title`, `description`, `questions` |

Gli elementi annidati senza `id` proprio usano un'altra chiave:

| Campo | Chiave | Contenuto |
|---|---|---|
| `images` | `path` dell'immagine | `{ title, alt }` |
| `history` | posizione nell'array (stesso ordine del file base) | `{ title, description }` |
| `stops` | `monument_id` della tappa | `{ note }` |
| `questions` | `id` della domanda | `{ text, options: { <id opzione>: "testo" }, explanation }` |
| `audio` | — | oggetto **completo** che sostituisce quello base (`path` in `media/audio/<lingua>/`, `language: "<lingua>"`) |

```json
{
  "centro-storico": {
    "name": "Historic Centre Tour",
    "short_name": "Historic Centre",
    "stops": {
      "chiesa-madre-santa-maria-itria": { "note": "Starting point: the Mother Church." }
    }
  }
}
```

**Non vanno mai tradotti** (restano nei file base): `id`, `lat`/`lon`, `category`,
`difficulty`, `travel_mode`, `color`, `path`/`legs` degli itinerari, `correct` dei quiz,
i path delle immagini. I valori enumerati (`category`, `difficulty`, …) e le etichette
dell'interfaccia (Home, Tappe, Tour…) sono tradotti **nell'app**, non nei contenuti.

### Comportamento dell'app

1. **Lingua iniziale:** preferenza salvata → altrimenti lingua del dispositivo se presente
   in `available_languages` → altrimenti `default_language`.
2. **Selettore** (sezione Info): mostra solo `available_languages`; se c'è una sola lingua
   il selettore è nascosto. Al cambio salva la preferenza e ricarica i contenuti.
3. **Unione:** carica il file base, poi se la lingua non è la predefinita carica la
   traduzione e sovrascrive i campi presenti. **Un testo mancante resta nella lingua
   predefinita**: le traduzioni possono essere parziali.
4. **Audio:** se un monumento non ha `audio` tradotto si usa quello base; l'app legge
   `audio.language` e può mostrare un'etichetta tipo *"Italian only"*.
5. **Cache:** separata per lingua, invalidata da `content_version` come per i file base.

Le versioni dell'app precedenti allo schema 1.1 ignorano `translations` e continuano a
funzionare in italiano.

`validate.py` controlla che le traduzioni puntino a id esistenti e contengano solo campi
traducibili (**errore**), e segnala i testi non ancora tradotti (**avviso**).

---

## Checklist per un nuovo comune

1. **Clona** una sottocartella esistente (es. `Comune di Bugliano/`) e rinominala `Comune di <Nome>/`.
2. In `config.json`: aggiorna `comune` (compreso `map_center`), `app.display_name`, i colori, **`media.base_url`** (deve puntare al repo/host del nuovo comune) e **`app.share_url`** (`…/heritage-pages/<Nome>/`, iniziale maiuscola).
3. In `manifest.json`: aggiorna `comune_id` e `content_version`.
4. Compila `monuments.json`, `itineraries.json`, `quizzes.json`.
5. Carica i media nelle cartelle `media/...` con gli stessi path indicati nei JSON.
   *(Opzionale)* aggiungi le traduzioni in `i18n/<lingua>/` e registrale nel manifest
   (vedi *Traduzioni*).
6. **Mappa:** verifica che `config.json` abbia `map.config_url` (lo stesso per tutti i
   comuni). Non duplicare la chiave: provider e chiave sono globali in `map.config.json`
   (radice di questo repo).
7. **Catalogo:** aggiungi il comune a `catalog.json` con `status: "preview"` (stesso `id`
   di `comune_id`, `center` e `radius_km` del territorio) ed esegui
   `python3 validate_catalog.py` nella radice. Provalo con una build preview dell'app.
8. **Pubblicazione:** quando è pronto porta `status` a `"published"`: il comune compare
   nell'app Heritage per tutti, **senza** nuove pubblicazioni sugli store.
9. **Landing page:** nel repo `heritage-pages` clona `Niscemi/` in `<Nome>/`, adatta testi e
   colori (gli stessi di `app.theme`); i link agli store sono quelli dell'app Heritage, il
   pulsante "Apri nell'app" usa `heritage://comune/<id>`.
10. **QR:** genera il QR da `app.share_url`, aprilo da smartphone e verifica che la pagina
    si carichi prima di mandarlo in stampa.

## Validazione consigliata

Prima di pubblicare, **entra nella cartella del comune** ed esegui `python3 validate.py`:
verifica che ogni `path` esista davvero e che ogni `monument_id` referenziato in
itinerari/quiz corrisponda a un id presente in `monuments.json`. Un piccolo script di
validazione evita schermate vuote nell'app.

```
cd "Comune di Niscemi"
python3 validate.py
```
