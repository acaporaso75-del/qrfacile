# /opt/qrfacile/qrfacile_app/pricing_config.py

"""
Configurazione unica dei prezzi QRFACILE.

Regola commerciale definitiva:
- 1 credito wine = 1 QR vino standard, pagina attiva/modificabile 10 anni.
- 2 crediti wine = 1 QR vino esteso, pagina attiva/modificabile 25 anni.
- Upgrade da 10 a 25 anni = 1 credito wine aggiuntivo.
- I crediti servono per creare nuovi QR o fare upgrade.
- I QR già creati restano online e modificabili per la durata scelta.
- Nessun abbonamento obbligatorio.

Importante:
- I pacchetti QR self-service caricano crediti.
- I servizi assistiti NON caricano crediti automaticamente.
- PayPal deve leggere i pacchetti da qui, così pagina prezzi,
  billing e pagamento restano coerenti.
"""

CURRENCY = "EUR"

FREE_WINE_CREDITS_ON_REGISTER = 3

QR_STANDARD_YEARS = 10
QR_EXTENDED_YEARS = 25

QR_STANDARD_CREDIT_COST = 1
QR_EXTENDED_CREDIT_COST = 2
QR_UPGRADE_10_TO_25_CREDIT_COST = 1


# =========================================================
# PACCHETTI QR VINO
# =========================================================

QR_PACKS = {
    "start": {
        "label": "Start",
        "subtitle": "Per piccole cantine o prime prove operative",
        "credit_type": "wine",
        "qty": 20,
        "amount_cents": 2900,
        "highlight": False,
        "features": [
            "20 crediti QR vino",
            "20 QR vino da 10 anni oppure 10 QR vino da 25 anni",
            "Nessun abbonamento obbligatorio",
            "Export QR pronto per tipografia",
        ],
    },
    "pro": {
        "label": "Cantina",
        "subtitle": "Per aziende con più vini e lotti",
        "credit_type": "wine",
        "qty": 60,
        "amount_cents": 7900,
        "highlight": True,
        "features": [
            "60 crediti QR vino",
            "60 QR vino da 10 anni oppure 30 QR vino da 25 anni",
            "Ideale per cantine operative",
            "Gestione lotti, etichette e QR",
        ],
    },
    "plus": {
        "label": "Business",
        "subtitle": "Per produzioni importanti e molti lotti",
        "credit_type": "wine",
        "qty": 200,
        "amount_cents": 19900,
        "highlight": False,
        "features": [
            "200 crediti QR vino",
            "200 QR vino da 10 anni oppure 100 QR vino da 25 anni",
            "Costo molto competitivo per grandi produzioni",
            "Adatto a molte referenze e lotti",
        ],
    },
}


# =========================================================
# SERVIZI ASSISTITI
# =========================================================

ASSISTED_SERVICES = {
    "assisted_base": {
        "label": "Avvio assistito base",
        "subtitle": "Per piccole cantine o prime etichette",
        "amount_cents": 7900,
        "features": [
            "Supporto iniziale fino a 5 QR",
            "Verifica dati principali",
            "Aiuto alla prima esportazione QR",
            "Servizio opzionale, separato dai crediti",
        ],
    },
    "assisted_winery": {
        "label": "Avvio assistito cantina",
        "subtitle": "Per chi deve partire con più vini o lotti",
        "amount_cents": 14900,
        "features": [
            "Supporto iniziale fino a 20 QR",
            "Organizzazione dati e lotti",
            "Supporto allo studio grafico",
            "Servizio opzionale, separato dai crediti",
        ],
    },
    "massive_import": {
        "label": "Import massivo / grandi cantine",
        "subtitle": "Per aziende con molte referenze o esigenze operative specifiche",
        "amount_cents": None,
        "features": [
            "Importazione dati",
            "Configurazione cantina",
            "Supporto a studi grafici e tipografie",
            "Preventivo personalizzato",
        ],
    },
}


# =========================================================
# HELPERS BASE
# =========================================================

def euro(amount_cents: int | None) -> str:
    if amount_cents is None:
        return "Su richiesta"

    euros = amount_cents / 100

    if euros.is_integer():
        return f"{int(euros)}€"

    return f"{euros:.2f}€".replace(".", ",")


def get_qr_pack(pack_key: str) -> dict | None:
    return QR_PACKS.get((pack_key or "").strip().lower())


def list_qr_packs() -> list[tuple[str, dict]]:
    return list(QR_PACKS.items())


def list_assisted_services() -> list[tuple[str, dict]]:
    return list(ASSISTED_SERVICES.items())


def credit_cost_for_duration(years: int) -> int:
    try:
        y = int(years)
    except Exception:
        y = QR_STANDARD_YEARS

    if y == QR_EXTENDED_YEARS:
        return QR_EXTENDED_CREDIT_COST

    return QR_STANDARD_CREDIT_COST


def duration_label(years: int) -> str:
    try:
        y = int(years)
    except Exception:
        y = QR_STANDARD_YEARS

    if y == QR_EXTENDED_YEARS:
        return f"{QR_EXTENDED_YEARS} anni · {QR_EXTENDED_CREDIT_COST} crediti"

    return f"{QR_STANDARD_YEARS} anni · {QR_STANDARD_CREDIT_COST} credito"


# =========================================================
# LEGACY / COMPATIBILITA BILLING-PAYPAL
# =========================================================

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
        "price": "€29",
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
        "desc": "Supporto professionale continuativo, gestione ricorrente e priorità operativa QRFACILE.",
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


# =========================================================
# ADAPTERS
# =========================================================

def _desc_from_features(data: dict) -> str:
    features = [
        str(x).strip()
        for x in (data.get("features") or [])
        if str(x).strip()
    ]

    return ". ".join(features[:2]) + ("." if features else "")


def _qr_pack_payload(key: str, pack: dict) -> dict:
    qty = int(pack.get("qty") or 0)

    return {
        "name": pack.get("label") or key,
        "price": euro(pack.get("amount_cents")),
        "amount_cents": int(pack.get("amount_cents") or 0),

        "wine_credits":
            qty if (pack.get("credit_type") or "wine") == "wine" else 0,

        "generic_credits":
            qty if pack.get("credit_type") == "generic" else 0,

        "desc":
            _desc_from_features(pack)
            or (pack.get("subtitle") or ""),

        "subscription": False,
        "kind": "qr_pack",
        "highlight": bool(pack.get("highlight")),
    }


def _assisted_payload(
    requested_key: str,
    service_key: str,
    service: dict,
) -> dict:

    amount = service.get("amount_cents")
    disabled = amount is None or int(amount or 0) <= 0

    return {
        "name": service.get("label") or requested_key,

        "price":
            euro(amount)
            if amount is not None
            else "Su richiesta",

        "amount_cents": int(amount or 0),

        "wine_credits": 0,
        "generic_credits": 0,

        "desc":
            _desc_from_features(service)
            or (service.get("subtitle") or ""),

        "subscription": False,
        "disabled": disabled,
        "hidden_in_billing": disabled,
        "kind": "assisted_service",
        "canonical_key": service_key,
    }


# =========================================================
# PUBLIC API
# =========================================================

def get_purchase_pack(pack_key: str) -> dict | None:
    key = (pack_key or "").strip().lower()

    # QR canonici
    if key in QR_PACKS:
        return _qr_pack_payload(key, QR_PACKS[key])

    # servizi assistiti + alias legacy
    if key in ASSISTED_SERVICE_ALIASES:
        service_key = ASSISTED_SERVICE_ALIASES[key]
        service = ASSISTED_SERVICES.get(service_key)

        if service:
            return _assisted_payload(
                key,
                service_key,
                service,
            )

    # legacy
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

