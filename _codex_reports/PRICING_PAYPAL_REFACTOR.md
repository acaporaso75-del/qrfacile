# Refactor controllato pricing/paypal QRFACILE

Data analisi: 2026-05-16

File analizzati:
- `qrfacile_app/pricing_config.py`
- `qrfacile_app/billing_ui.py`
- `qrfacile_app/paypal_ui.py`

## Stato attuale

`pricing_config.py` contiene gia' la fonte canonica per:
- `QR_PACKS`: pacchetti self-service wine (`start`, `pro`, `plus`);
- `ASSISTED_SERVICES`: servizi assistiti (`assisted_base`, `assisted_winery`, `massive_import`);
- costanti di prezzo/durata/crediti;
- helper `euro()`, `get_qr_pack()`, `list_qr_packs()`, `list_assisted_services()`.

`pricing_ui.py` usa gia' `pricing_config.py`.

`billing_ui.py` e `paypal_ui.py` duplicano invece una mappa locale `PACKS`, con formato diverso:
- `name` invece di `label`;
- `price` stringa gia' formattata in `billing_ui.py`;
- `wine_credits` / `generic_credits` invece di `credit_type` + `qty`;
- chiavi legacy non presenti in `pricing_config.py`: `unlimited`, `generic_10`, `assistenza_start`, `assistenza_completa`, `assistenza_premium`, `assistenza_continuativa`.

Queste chiavi legacy sono ancora importanti:
- `generic_10` non va rotto per i generic credits legacy;
- `unlimited` rimane disabilitato/non acquistabile online ma puo' comparire in suggerimenti storici;
- `assistenza_*` sono attualmente acquistabili o visibili in billing/PayPal, ma i corrispondenti canonici hanno nomi diversi in `ASSISTED_SERVICES`.

## 1. Piano patch

### Patch A - aggiungere adapter compatibile in `pricing_config.py`

Obiettivo: mantenere `pricing_config.py` come unica fonte di verita' per prezzi/pacchetti nuovi, ma preservare compatibilita' con i formati attesi da UI e PayPal.

Aggiungere in fondo a `pricing_config.py`:
- `LEGACY_PACKS`: solo voci non presenti nei pacchetti canonici e necessarie per compatibilita';
- `ASSISTED_SERVICE_ALIASES`: mapping dalle chiavi storiche alle nuove chiavi canoniche;
- `pack_to_legacy_payload(key, data, *, price=False)`: adapter verso il formato `PACKS` storico;
- `get_purchase_pack(pack_key)`: risolve pack canonici, servizi assistiti con alias e legacy;
- `list_billing_packs()`: lista ordinata per `billing_ui.py`;
- opzionale `list_paypal_packs()` se si vuole una separazione esplicita tra visibile in UI e validabile da PayPal.

Motivo: sposta la duplicazione fuori da `billing_ui.py`/`paypal_ui.py` e centralizza anche la compatibilita' legacy nello stesso file.

### Patch B - refactor `billing_ui.py`

Sostituire la definizione locale `PACKS` con import da `pricing_config.py`.

Import consigliato:

```python
from qrfacile_app.pricing_config import get_purchase_pack, list_billing_packs
```

Aggiornare:
- `_plan_label(plan)` per usare `get_purchase_pack(plan)` come fonte primaria, con fallback al dizionario minimale esistente solo se serve;
- `pack_labels` in `billing()` generandolo da `list_billing_packs()` e/o dai canonici `QR_PACKS`;
- `visible_packs = [(k, v) for k, v in list_billing_packs() if not v.get("hidden_in_billing")]`;
- `_pack_card()` lasciando invariata la UI attuale, perche' ricevera' ancora `name`, `price`, `desc`, `wine_credits`, `generic_credits`;
- `request_plan()` usando `get_purchase_pack(pack)` invece di `PACKS[pack]`.

Nota: se non si vuole piu' mostrare servizi assistiti dentro billing, filtrare con `v.get("kind") == "qr_pack"` mantenendo comunque validazione PayPal per gli alias legacy.

### Patch C - refactor `paypal_ui.py`

Sostituire la definizione locale `PACKS` con:

```python
from qrfacile_app.pricing_config import get_purchase_pack
```

Aggiornare:
- in `/paypal/start`: `data = get_purchase_pack(pack)` e controllo `if not data`;
- controllo non acquistabile: `data.get("disabled") or int(data.get("amount_cents") or 0) <= 0`;
- descrizione PayPal: `data["name"]`;
- importo ordine: `data["amount_cents"]`;
- in `/paypal/return`: stessa risoluzione tramite `get_purchase_pack(pack)`;
- accredito crediti invariato, leggendo `wine_credits` e `generic_credits`.

Non cambiare:
- endpoint `/paypal/start`;
- endpoint `/paypal/return`;
- parametri form `pack` e `billing_winery_id`;
- tabella `orders`;
- logica di capture e idempotenza;
- logica generic credits.

## 2. Elenco rischi

1. **Mismatch chiavi servizi assistiti**
   - `pricing_config.py` usa `assisted_base`, `assisted_winery`, `massive_import`.
   - UI/PayPal storici usano `assistenza_start`, `assistenza_completa`, `assistenza_premium`.
   - Rischio: ordini storici o form vecchi falliscono se gli alias non sono mantenuti.

2. **Generic credits legacy**
   - `generic_10` non esiste in `QR_PACKS`.
   - Rischio: rimuoverlo del tutto romperebbe acquisto/caricamento di crediti generic.
   - Mitigazione: tenerlo in `LEGACY_PACKS` dentro `pricing_config.py`.

3. **Unlimited legacy**
   - `unlimited` e' ancora accettato come suggested pack e in alcuni form, ma deve restare non acquistabile online.
   - Rischio: adapter troppo permissivo lo renda acquistabile.
   - Mitigazione: `disabled=True`, `amount_cents=0`, `hidden_in_billing=True` o filtro equivalente.

4. **Visibilita' billing**
   - Oggi `billing_ui.py` mostra tutti i `PACKS` tranne `unlimited`, quindi mostra anche generic e assistenze.
   - Se la patch mostra solo `QR_PACKS`, cambia comportamento UI.
   - Mitigazione: decidere esplicitamente se mantenere la stessa visibilita'. Per compatibilita' stretta, mantenere anche `generic_10`, `assistenza_start`, `assistenza_completa`, `assistenza_continuativa`; tenere fuori `unlimited` e `assistenza_premium` se non acquistabile.

5. **Ordini pending esistenti**
   - `/paypal/return` risolve `locked_order.pack`.
   - Rischio: un ordine pending creato prima della patch con chiave legacy non piu' risolta non puo' essere completato.
   - Mitigazione: `get_purchase_pack()` deve riconoscere tutte le chiavi oggi presenti in `PACKS`.

6. **Descrizioni/prezzi UI**
   - `billing_ui.py` si aspetta `price`, `desc`, `name`.
   - `QR_PACKS` ha `label`, `subtitle`, `features`.
   - Mitigazione: adapter che produce payload storico, invece di modificare profondamente `_pack_card()`.

7. **Servizi assistiti senza crediti**
   - PayPal oggi registra ordine paid ma non accredita crediti, coerente con commento in `pricing_config.py`.
   - Rischio: convertire ogni item in `credit_type` + `qty` senza distinguere servizi potrebbe caricare crediti per errore.
   - Mitigazione: per assisted service impostare `wine_credits=0`, `generic_credits=0`, `kind="assisted_service"`.

## 3. Patch consigliate

### 3.1 Adapter suggerito in `pricing_config.py`

```python
LEGACY_PACKS = {
    "unlimited": {
        "name": "Unlimited legacy",
        "price": "Non disponibile online",
        "amount_cents": 0,
        "wine_credits": 0,
        "generic_credits": 0,
        "desc": "Piano legacy/deprecato. Non usarlo per nuovi acquisti self-service.",
        "disabled": True,
        "hidden_in_billing": True,
        "kind": "legacy",
    },
    "generic_10": {
        "name": "QR Link 10",
        "price": euro(2900),
        "amount_cents": 2900,
        "wine_credits": 0,
        "generic_credits": 10,
        "desc": "10 crediti per QR link esterni/generici.",
        "kind": "generic_credits",
    },
    "assistenza_continuativa": {
        "name": "Assistenza QRFACILE Continuativa",
        "price": "1200€ / anno",
        "amount_cents": 120000,
        "wine_credits": 0,
        "generic_credits": 0,
        "desc": "Supporto professionale continuativo, gestione ricorrente e priorita' operativa QRFACILE.",
        "kind": "assisted_service",
    },
}

ASSISTED_SERVICE_ALIASES = {
    "assistenza_start": "assisted_base",
    "assistenza_completa": "assisted_winery",
    "assistenza_premium": "massive_import",
    "assisted_base": "assisted_base",
    "assisted_winery": "assisted_winery",
    "massive_import": "massive_import",
}

def _desc_from_features(data: dict) -> str:
    features = [str(x).strip() for x in (data.get("features") or []) if str(x).strip()]
    return ". ".join(features[:2]) + ("." if features else "")

def _qr_pack_payload(key: str, pack: dict) -> dict:
    qty = int(pack.get("qty") or 0)
    return {
        "name": pack.get("label") or key,
        "price": euro(pack.get("amount_cents")),
        "amount_cents": int(pack.get("amount_cents") or 0),
        "wine_credits": qty if (pack.get("credit_type") or "wine") == "wine" else 0,
        "generic_credits": qty if pack.get("credit_type") == "generic" else 0,
        "desc": _desc_from_features(pack) or (pack.get("subtitle") or ""),
        "subscription": False,
        "kind": "qr_pack",
        "highlight": bool(pack.get("highlight")),
    }

def _assisted_payload(requested_key: str, service_key: str, service: dict) -> dict:
    amount = service.get("amount_cents")
    disabled = amount is None or int(amount or 0) <= 0
    return {
        "name": service.get("label") or requested_key,
        "price": euro(amount) if amount is not None else "Su richiesta",
        "amount_cents": int(amount or 0),
        "wine_credits": 0,
        "generic_credits": 0,
        "desc": _desc_from_features(service) or (service.get("subtitle") or ""),
        "subscription": False,
        "disabled": disabled,
        "hidden_in_billing": disabled,
        "kind": "assisted_service",
        "canonical_key": service_key,
    }

def get_purchase_pack(pack_key: str) -> dict | None:
    key = (pack_key or "").strip().lower()
    if key in QR_PACKS:
        return _qr_pack_payload(key, QR_PACKS[key])
    if key in ASSISTED_SERVICE_ALIASES:
        service_key = ASSISTED_SERVICE_ALIASES[key]
        service = ASSISTED_SERVICES.get(service_key)
        if service:
            return _assisted_payload(key, service_key, service)
    if key in LEGACY_PACKS:
        return dict(LEGACY_PACKS[key])
    return None

def list_billing_packs() -> list[tuple[str, dict]]:
    keys = [
        *QR_PACKS.keys(),
        "generic_10",
        "assistenza_start",
        "assistenza_completa",
        "assistenza_premium",
        "assistenza_continuativa",
        "unlimited",
    ]
    out = []
    for key in keys:
        data = get_purchase_pack(key)
        if data:
            out.append((key, data))
    return out
```

Nota: `price` per `generic_10` diventerebbe `29€` invece dell'attuale `€29`. Se serve compatibilita' visiva letterale, impostare `"price": "€29"` nel legacy pack.

### 3.2 Diff concettuale `billing_ui.py`

```diff
-PACKS = {...}
+from qrfacile_app.pricing_config import get_purchase_pack, list_billing_packs
```

```diff
-    labels = {...}
-    return labels.get((plan or "").strip().lower(), plan or "-")
+    data = get_purchase_pack(plan)
+    if data:
+        return data.get("name") or plan or "-"
+    return plan or "-"
```

```diff
-    visible_packs = [(k, v) for k, v in PACKS.items() if k not in hidden_packs]
+    visible_packs = [
+        (k, v)
+        for k, v in list_billing_packs()
+        if not v.get("hidden_in_billing") and k not in hidden_packs
+    ]
```

```diff
-    if pack not in PACKS:
+    data = get_purchase_pack(pack)
+    if not data:
         raise HTTPException(400, "Piano non valido")
-
-    data = PACKS[pack]
```

### 3.3 Diff concettuale `paypal_ui.py`

```diff
-PACKS = {...}
+from qrfacile_app.pricing_config import get_purchase_pack
```

```diff
-    if pack not in PACKS:
+    data = get_purchase_pack(pack)
+    if not data:
         raise HTTPException(400, "Pacchetto non valido")
-
-    data = PACKS[pack]
```

Stessa sostituzione dentro `/paypal/return`:

```diff
-            if pack not in PACKS:
+            data = get_purchase_pack(pack)
+            if not data:
                 raise HTTPException(400, "Pacchetto ordine non valido")
-
-            data = PACKS[pack]
```

## 4. Ordine esecuzione consigliato

1. Aggiungere adapter e legacy compatibility in `pricing_config.py`.
2. Eseguire test/import rapido su `pricing_config.py`:
   - `start`, `pro`, `plus` risolti;
   - `generic_10` risolto con `generic_credits=10`;
   - `assistenza_start` e `assistenza_completa` risolti dagli alias;
   - `assistenza_premium`/`massive_import` disabilitati per importo `None`;
   - `unlimited` disabilitato.
3. Refactor `paypal_ui.py`, perche' e' il punto piu' critico: validazione pack, importo, accredito.
4. Refactor `billing_ui.py` mantenendo `_pack_card()` quasi invariata.
5. Smoke test manuale o con `TestClient` sugli endpoint senza chiamare PayPal reale, mockando `_paypal_token` e `requests.post`.
6. Solo dopo smoke positivo, valutare pulizia ulteriore di label statiche (`pack_labels`) e naming servizi.

## 5. Test smoke

### Smoke import/config

```bash
python - <<'PY'
from qrfacile_app.pricing_config import get_purchase_pack, list_billing_packs

for key in ["start", "pro", "plus", "generic_10", "assistenza_start", "assistenza_completa", "assistenza_premium", "unlimited"]:
    data = get_purchase_pack(key)
    assert data, key
    print(key, data["name"], data["amount_cents"], data.get("wine_credits"), data.get("generic_credits"), data.get("disabled"))

assert get_purchase_pack("start")["wine_credits"] == 20
assert get_purchase_pack("pro")["amount_cents"] == 7900
assert get_purchase_pack("generic_10")["generic_credits"] == 10
assert get_purchase_pack("assistenza_start")["amount_cents"] == 7900
assert get_purchase_pack("assistenza_completa")["amount_cents"] == 14900
assert get_purchase_pack("assistenza_premium")["disabled"] is True
assert get_purchase_pack("unlimited")["disabled"] is True
assert [k for k, _ in list_billing_packs()][:3] == ["start", "pro", "plus"]
PY
```

### Smoke UI billing

Con utente winery/admin autenticato:
- aprire `/app/billing`;
- verificare che le card `Start`, `Cantina`, `Business` abbiano importi e crediti corretti;
- verificare che `generic` sia ancora visibile nel saldo;
- verificare che `unlimited` non sia acquistabile/visibile come pack online;
- se si mantengono i servizi in billing, verificare card servizi senza accredito crediti.

### Smoke PayPal start con mock

Mockare:
- `_paypal_token()` -> `"fake-token"`;
- `requests.post()` per `/v2/checkout/orders` -> JSON con `id` e link `approve`.

Verificare:
- `POST /paypal/start pack=start` crea `orders.pack='start'`, `amount_cents=2900`;
- `POST /paypal/start pack=generic_10` crea ordine da `2900`;
- `POST /paypal/start pack=assistenza_start` crea ordine da `7900`;
- `POST /paypal/start pack=unlimited` risponde `400`;
- `POST /paypal/start pack=assistenza_premium` risponde `400`;
- endpoint e parametri restano invariati.

### Smoke PayPal return con mock

Preparare ordine pending e mockare capture PayPal `COMPLETED`.

Verificare:
- ordine `start`: status `paid`, ledger `wine +20`;
- ordine `pro`: ledger `wine +60`;
- ordine `plus`: ledger `wine +200`;
- ordine `generic_10`: ledger `generic +10`;
- ordine `assistenza_start`: status `paid`, nessun movimento credito;
- doppio return sullo stesso ordine non duplica crediti.

## Raccomandazione finale

Patch minima e sicura: non modificare il comportamento dei flussi, ma introdurre un adapter centrale in `pricing_config.py` che espone ancora il payload storico atteso da `billing_ui.py` e `paypal_ui.py`.

Questo permette di rimuovere i `PACKS` duplicati dai due file, rendere `QR_PACKS` e `ASSISTED_SERVICES` la fonte dei prezzi canonici e preservare tutte le chiavi legacy necessarie a PayPal, ordini pending e generic credits.
