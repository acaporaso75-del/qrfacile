# QRFACILE Premium UI Plan

Data analisi: 2026-05-16

Ambito analizzato:
- `qrfacile_app/public.py`
- `qrfacile_app/dashboard_ui.py`
- `qrfacile_app/studio_area.py`
- `qrfacile_app/billing_ui.py`
- `qrfacile_app/pricing_ui.py`
- `qrfacile_app/ui_shell.py`
- `static/app.css`

Vincoli rispettati: nessuna modifica ai file applicativi, nessuna patch, nessuna lettura di `.env`. Unica scrittura prevista: questo report.

## 1. Linee Guida Design System

QRFACILE deve comunicare affidabilita, controllo operativo e qualita B2B. Il riferimento estetico corretto e un SaaS verticale premium per asset critici stampati su bottiglia, non una web app consumer decorativa.

### Direzione visiva

- Sobrio, tecnico, internazionale.
- Superfici chiare, gerarchia forte, accenti misurati.
- Meno decorazione, piu leggibilita e controllo.
- Niente emoji come iconografia primaria.
- Card meno arrotondate e meno ombreggiate.
- Gradienti usati solo per hero o stati speciali, non come linguaggio onnipresente.

### Palette consigliata

- Background app: `#f6f8fb`
- Surface primaria: `#ffffff`
- Surface secondaria: `#f9fafb`
- Testo primario: `#111827`
- Testo secondario: `#667085`
- Linee: `#e5e7eb`
- Accent principale: teal istituzionale `#0f766e`
- Accent secondario: blue tecnico `#1d4ed8`
- Success: `#067647`
- Warning: `#b54708`
- Danger: `#b42318`
- Premium accent: oro spento `#b68a35`, solo per badge o piano evidenziato.

Da ridurre: dominanza mint/sky/lavanda, gradienti radiali multipli, pastel diffusi su sidebar e hero interni.

### Tipografia

- Mantenere system font, ma ridurre l'abuso di `font-weight:950`.
- H1 app: 32-36px desktop, 28-30px mobile.
- Titoli card: 17-19px.
- Testo operativo: 14-15px.
- Meta/label: 11-12px, uppercase solo per label tecniche.
- Riservare pesi 900/950 a headline e metriche, non a ogni elemento.
- Evitare letter-spacing negativo nei pannelli operativi.

### Shape, spacing, ombre

- Card app: radius 16-18px.
- Hero/pannelli principali: radius 22px.
- Bottoni/input: radius 12-14px.
- Pill: 999px.
- Spacing base: 8px.
- Shadow default: `0 8px 24px rgba(16,24,40,.06)`.
- Shadow importante: `0 16px 48px rgba(16,24,40,.08)`.

Oggi `static/app.css` usa radius 24/28px e shadow ampie: effetto ricco, ma meno enterprise.

## 2. Priorita Estetiche P0/P1/P2

### P0

1. Rimuovere emoji dalle aree operative principali: sidebar, Studio, Billing, Dashboard.
2. Centralizzare hero interni: Dashboard e Billing duplicano pattern simili con CSS embedded.
3. Rendere `btn-primary` piu enterprise: colore pieno teal, testo bianco, hover sobrio.
4. Standardizzare card, badge, note, empty state, metriche.
5. Ridurre gradienti e ombre globali nel CSS.
6. Rendere Pricing e Billing coerenti: stesso linguaggio per piani, crediti, badge e CTA.

### P1

1. Migrare CSS embedded da `dashboard_ui.py`, `billing_ui.py`, `pricing_ui.py` verso `static/app.css`.
2. Rendere sidebar piu professionale: icone lineari, stato attivo, meno tile decorativi.
3. Compattare card dashboard per lotti numerosi.
4. Migliorare tabelle Studio/Billing con panel coerenti e header piu leggibili.
5. Pulire la pagina QR pubblica da emoji e renderla piu istituzionale.

### P2

1. Introdurre tema enterprise come default visivo.
2. Aggiungere vista compatta per Dashboard e Studio.
3. Rafforzare microcopy internazionale e B2B.
4. Preparare libreria icone interna o SVG sprite.
5. Valutare dark mode solo dopo consolidamento del design system.

## 3. Modifiche Consigliate File per File

### `qrfacile_app/ui_shell.py`

Ruolo: shell centrale, topbar, sidebar, page wrapper.

Consigli:
- sostituire emoji della nav con icone centralizzate o classi semantiche;
- introdurre helper `icon(name)`, `status_badge()`, `page_hero()`, `metric_card()`, `empty_state()`;
- rendere `top_actions()` capace di gestire variante primary/secondary/danger;
- aggiungere stato attivo alla sidebar;
- migliorare label:
  - “Scala 1 wine” -> “Creazione QR vino”;
  - “3 gratis + generic” -> “QR link esterni”;
  - “Pacchetti” -> “Saldo e acquisto”;
  - “Approve & paid” -> “Approvazioni payout”.

### `static/app.css`

Ruolo: fondazione visiva.

Consigli:
- ridurre background globale da tre radial gradient a base neutra con accento leggero;
- abbassare radius globali (`--r:18px`, `--r2:14px`, `--r3:10px`);
- ridurre shadow globali;
- cambiare `btn-primary` da gradiente mint/sky a teal pieno;
- limitare `card:hover` alle card cliccabili;
- aggiungere classi componenti: `.pageHero`, `.metricCard`, `.statusBadge`, `.iconBox`, `.emptyState`, `.planCard`, `.tablePanel`, `.notice`, `.actionBar`.

### `qrfacile_app/dashboard_ui.py`

Ruolo: area lotti e controllo operativo.

Consigli:
- sostituire CSS embedded del dashboard hero con `.pageHero`;
- sostituire `dashboardEmptyIcon` con `iconBox` neutro;
- rendere `dashboardWineCard` meno grande e meno decorativa;
- usare `StatusBadge` per compliance e stato;
- sostituire `✓` e `!` dei mini-check con icone CSS/SVG;
- tenere una sola CTA primaria nella toolbar, preferibilmente “Nuovo lotto”.

### `qrfacile_app/studio_area.py`

Ruolo: workflow studio grafico, inviti, clienti, etichette.

Consigli:
- ridurre inline style e introdurre classi dedicate;
- sostituire pill con emoji con badge testuali: “Vini”, “Etichette”, “Pubblicate”, “Piano suggerito”;
- trasformare “Come proporre QRFACILE alla Cantina” in pannello operativo piu sobrio;
- separare chiaramente creazione invito, cantine collegate, ultimi inviti;
- rendere card cantina piu compatte e confrontabili;
- mantenere invariati form action, input name e JS copia link.

### `qrfacile_app/billing_ui.py`

Ruolo: monetizzazione, crediti, fiducia.

Consigli:
- riusare `pageHero` e `metricCard`;
- sostituire `ℹ️` e `📄` con `iconBox`;
- trasformare `_pack_card()` in componente condivisibile con Pricing;
- evitare griglia a 5 colonne se i piani diventano compressi: meglio 3 colonne desktop con gerarchia chiara;
- rendere badge “Consigliato” piu sobrio;
- distinguere meglio wine/generic con testo, non solo colore.

### `qrfacile_app/pricing_ui.py`

Ruolo: pagina prezzi pubblica.

Consigli:
- eliminare `★`, `✓` unicode ed emoji;
- usare bullet CSS o icone lineari;
- allineare visualmente plan card a Billing;
- rendere credit rules una strip tecnica o tabella comparativa;
- trasformare security section in blocco trust enterprise senza emoji;
- mantenere invariati form `/paypal/start` e link registrazione.

### `qrfacile_app/public.py`

Ruolo: pagina QR pubblica dopo scansione.

Consigli:
- mantenere struttura informativa: e gia chiara;
- rimuovere emoji da riciclo, ingredienti, allergeni, nutrizione;
- sostituire component icon con abbreviazioni professionali o SVG lineari: `GL`, `CAP`, `SEAL`, `LBL`, `BOX`, `REC`;
- ridurre watermark `INCOMPLETO` su mobile: puo sembrare errore grave all'utente finale;
- mantenere lingua, tracking, status e logica compliance invariati;
- in seguito spostare CSS embedded in `static/public_label.css`.

## 4. Emoji Da Rimuovere

### P0 operative

`qrfacile_app/ui_shell.py`:
- `🏠`, `📋`, `🍷`, `🔗`, `💳`, `🏷️`, `🎨`, `⚙️`, `💶`, `📊`, `🧾`, `🔓`, `🛠️`

`qrfacile_app/studio_area.py`:
- `🍷`, `🏷`, `🌍`, `💡`

`qrfacile_app/billing_ui.py`:
- `ℹ️`, `📄`

`qrfacile_app/dashboard_ui.py`:
- `🍷`
- valutare sostituzione di `✓` e `!`

### P1 pubbliche/pricing

`qrfacile_app/pricing_ui.py`:
- `★`, `✓`, `🎁`, `👤`, `👥`, `🎧`, `☁️`, `🖥️`, `🖨️`

`qrfacile_app/public.py`:
- `🍾`, `🟤`, `🎗️`, `🏷️`, `📦`, `♻️`, `🍇`, `🛡️`, `⚖️`

## 5. Componenti Da Centralizzare

Da centralizzare subito in `ui_shell.py` + `static/app.css`:
- `PageHero`
- `MetricCard`
- `DataCard`
- `StatusBadge`
- `CreditBadge`
- `PlanCard`
- `ActionBar`
- `EmptyState`
- `TablePanel`
- `Notice`
- `IconBox`
- `ThumbnailPair`

Da centralizzare dopo:
- card riciclo pagina pubblica;
- card nutrizione;
- language switcher;
- componenti trust/security pricing.

## 6. Cosa Fare Prima Senza Rompere Funzioni

Ordine consigliato:

1. Aggiungere nuove classi CSS senza rimuovere le vecchie.
2. Aggiungere helper UI in `ui_shell.py` senza cambiare chiamate esistenti.
3. Sostituire le emoji della sidebar: cambio visivo localizzato.
4. Migrare Billing a componenti condivisi, senza toccare `/paypal/start`.
5. Migrare Dashboard hero, empty state e toolbar.
6. Migrare Studio card e inviti, mantenendo invariati form e JS copia link.
7. Migrare Pricing e allinearlo a Billing.
8. Intervenire su `public.py` per ultimo, con test su mobile e QR reali.

## 7. Cosa NON Toccare Ora

Non toccare:
- logica DB;
- query SQL;
- permessi `require_any_role`;
- route e URL;
- nomi dei campi form;
- flussi PayPal;
- tracking scan in `public.py`;
- scelta lingua;
- controlli compliance;
- upload path e asset path;
- file backup;
- landing routes fuori ambito;
- dark mode;
- cambio framework frontend;
- refactor template generale.

## 8. Come Far Sembrare QRFACILE Un Prodotto Premium Internazionale

- Usare meno copy promozionale e piu copy operativo: “Compliance-ready digital wine labels”, “Print-ready QR exports”, “Studio collaboration”.
- Rafforzare segnali di fiducia: dati societari, durata QR, backup, export professionale, permessi, audit trail.
- Eliminare visual infantili: emoji, gradienti eccessivi, pill troppo colorate.
- Rendere pricing e billing simili a prodotti SaaS internazionali: piani confrontabili, CTA coerenti, badge sobri.
- Usare lingua visiva coerente tra pubblico e app: stessa palette, stessi badge, stessa gerarchia.
- Dare piu spazio a prove di qualita: QR per tipografia, SVG/PDF/ZIP, multilingua, ruoli Studio/Cantina.
- Usare microcopy piu preciso: “QR link esterni” invece di “generic”, “Crediti QR vino” invece di “wine”.
- Evitare parole miste non governate come “Approve & paid”.

## 9. Suggerimenti UX Mobile

- Sidebar mobile: trasformarla in menu compatto o nav a sezioni, non in lista lunga di card.
- Bottoni: massimo una CTA primaria per blocco; secondarie sotto o in menu.
- Dashboard card: ridurre thumbs fronte/retro o renderle swipe/stack; oggi rischiano card troppo alte.
- Tabelle Studio/Billing: usare card rows mobile invece di tabella larga con scroll quando possibile.
- Pricing: una card per volta, piano consigliato non traslato verso l'alto su mobile.
- Pagina QR pubblica: hero piu compatto, meta grid a 2 colonne, card nutrizione leggibili senza scroll orizzontale.
- Evitare testo dentro bottoni troppo lunghi; usare label brevi.
- Language switcher pubblico sempre visibile ma non dominante.
- Watermark incomplete/draft meno invasivo sui piccoli schermi.

## 10. Suggerimenti Specifici Per Area Studio Grafico E Pagina QR Pubblica

### Area Studio Grafico

Obiettivo: far percepire lo Studio come una console clienti, non una pagina tutorial.

Consigli:
- Hero: “Clienti e inviti” con metriche: cantine collegate, inviti aperti, etichette assegnate.
- Form invito in pannello dedicato, con CTA primaria “Crea invito”.
- Sezione cantine come lista clienti compatta: logo, nome, permessi, piani, conteggi, CTA “Apri”.
- Ultimi inviti come tabella/panel con stato badge: “In attesa”, “Usato”, “Scaduto”.
- Rimuovere il blocco lungo “Come proporre QRFACILE” dalla parte alta o spostarlo in help/collapsible.
- Rendere il piano suggerito una select compatta con descrizione corta.
- Usare badge testuali per permessi: View, Edit, Create.

### Pagina QR Pubblica

Obiettivo: sembrare una scheda prodotto normativa affidabile, internazionale e consultabile da mobile.

Consigli:
- Mantenere header pulito con logo, lingua, stato.
- Dare centralita a vino e cantina, non all'icona QR.
- Ridurre decorazione e gradienti: il contenuto normativo deve sembrare ufficiale.
- Sostituire emoji delle sezioni con icone lineari o label testuali.
- Card ingredienti/allergeni/nutrizione/riciclo: stesso stile, stessa densita, stessa gerarchia.
- Riciclo: evidenziare codici materiali con pill tecniche, non icone colorate.
- Incomplete: mostrare warning chiaro ma non allarmistico per l'utente finale.
- Multilingua: IT/EN come segmented control sobrio.
- Footer: aggiungere riferimento QRFACILE/Enolab in modo discreto, rafforzando fiducia.

## Sintesi Esecutiva

QRFACILE ha gia una base funzionale forte e una UI ricca. Il salto premium non richiede piu decorazione: richiede normalizzazione. Il problema principale e la frammentazione visiva tra CSS globale, stili embedded e inline style, piu l'uso esteso di emoji come icone.

La traiettoria corretta e: token piu sobri, componenti centralizzati, iconografia coerente, meno gradienti, meno shadow, CTA piu disciplinate, Billing/Pricing allineati e pagina QR pubblica piu istituzionale. Il primo intervento a rischio basso e introdurre il design system senza rimuovere classi esistenti, poi migrare progressivamente sidebar, billing, dashboard, studio e pricing. La pagina pubblica QR va rifinita per ultima, con cautela.
