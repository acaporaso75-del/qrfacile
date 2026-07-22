# QRFACILE_REAL_USER_QA_AGENT

Ambiente testato: `http://192.168.1.139:8000`  
Data: 2026-05-20  
Modalita: QA non distruttiva. Non sono stati modificati file applicativi, non e' stato letto `.env`, non sono stati creati account, non sono stati cancellati dati, non sono stati eseguiti pagamenti reali.  
Metodo: smoke test HTTP GET/HEAD su pagine pubbliche/protette e analisi dei flussi gia' presenti nel codice.

## 1. Executive summary

La piattaforma e' vicina al varo pubblico per contenuto, copertura funzionale e chiarezza generale. Area pubblica, pricing, guide, manuali PDF, login, recupero password, inviti studio e pagine di errore principali sono presenti.

Blocco principale: le route protette da utente non loggato rispondono `303 See Other` ma senza header `Location`. Questo puo' impedire al browser di raggiungere `/login?expired=1` e blocca un utente reale che apre dashboard, area studio, preview protetta o ritorno PayPal senza sessione valida.

Esito finale: non pubblicabile finche' il P0 redirect non e' corretto e verificato.

## 2. Voto semplicita generale 1-10

**7/10**

La struttura e' comprensibile: Home, Pricing, Guide, Login, Dashboard, Area Studio. I messaggi principali sono generalmente chiari. Restano alcuni punti tecnici o ambigui: CTA di pubblicazione per studio, acquisti da pubblico, messaggi `Forbidden`, e duplicazioni di route/settings.

## 3. Voto linearita flusso Cantina 1-10

**7/10**

Il flusso Cantina e' logicamente ordinato: login, dashboard, nuovo lotto, compliance, preview, pubblicazione, export. Il controllo ownership e crediti e' coerente lato codice. Il problema e' che l'accesso da non loggato alle pagine protette puo' non redirigere correttamente al login.

## 4. Voto linearita flusso Studio 1-10

**7/10**

Il flusso Studio e' migliorato: invito pubblico chiaro, blocco email errata, accettazione, area studio, workspace cantina. Da testare end-to-end con account reali. La UX e' ancora migliorabile su mismatch email in registrazione e su azioni invito mancanti come annulla/reinvia.

## 5. Voto fiducia/commerciale 1-10

**7/10**

Pricing, Trust, Support e manuali danno buona fiducia. Per lancio commerciale servono prima: redirect login affidabile, reset password con migrazione DB applicata, test PayPal sandbox completo, e messaggi meno tecnici sugli errori.

## 6. Tabella scenari

| Scenario | Ruolo | Esito | Blocco UX | Gravita | Fix consigliato |
|---|---|---|---|---|---|
| A. Home | Utente non loggato | `200 OK` | Nessuno grave | P2 | Continuare a monitorare CTA principali |
| A. Pricing | Utente non loggato | `200 OK` | Acquisto richiede login, non sempre esplicitissimo | P2 | CTA tipo "Accedi per acquistare" |
| A. Guide | Utente non loggato | `200 OK` | Nessuno | P2 | Nessuno urgente |
| A. Trust | Utente non loggato | `200 OK` | Nessuno | P2 | Nessuno urgente |
| A. Support | Utente non loggato | `200 OK` | Nessuno | P2 | Nessuno urgente |
| A. Login | Utente non loggato | `200 OK`, contiene "Password dimenticata" | Nessuno | P2 | Nessuno urgente |
| A. Password dimenticata | Utente non loggato | `/forgot-password` `200`, CTA presente | Dipende da tabella reset token | P1 | Verificare migrazione `password_reset_tokens` applicata |
| A. Reset token non valido | Utente non loggato | `200`, messaggio "Link non valido" | Nessuno | P2 | OK |
| A. Download manuale cantina | Utente non loggato | PDF `200 OK` | Nessuno | P2 | OK |
| A. Download manuale studio | Utente non loggato | PDF `200 OK` | Nessuno | P2 | OK |
| A. Download manuale QR stampa | Utente non loggato | PDF `200 OK` | Nessuno | P2 | OK |
| B. Login Cantina | Cantina gia registrata | Non testato con credenziali reali; codice presente | Redirect protetto rotto se non loggata | P0 | Preservare `Location` nei redirect HTTPException 303 |
| B. Dashboard Cantina | Cantina non loggata | `303` senza `Location` | Browser puo' non andare al login | P0 | Fix handler globale in `qrfacile_app/main.py` |
| B. Creazione nuovo lotto | Cantina | Codice limita winery a owner/admin/studio autorizzato | Non testato con dati reali | P1 | Test manuale con account cantina |
| B. Selezione vino master | Cantina | Route presente; codice valida winery_id | Nessuno evidente | P2 | Test con account reale |
| B. Cantina non puo scegliere altre cantine | Cantina | Codice forza/valida owner winery | Nessuno evidente | P2 | Test reale di regressione |
| B. Compilazione dati obbligatori | Cantina | Flusso compliance presente | Potrebbe essere lungo per utente medio | P2 | Guida contestuale breve in dashboard |
| B. Preview tecnica | Cantina | ACL candidato/codice recente protegge preview | Se non loggata redirect rotto | P0/P1 | Fix redirect; test con QR reale |
| B. Pubblicazione pagina ufficiale | Cantina | Blocca dati incompleti; studio non pubblica | Messaggi tecnici possibili | P2 | Migliorare errori Forbidden |
| B. Apertura `/e/{slug}` | Pubblico | QR inesistente testato: `404` | OK | P2 | Test QR reale attivo |
| B. Export QR | Cantina | Route export presente | Non testato senza login | P1 | Test account reale |
| B. Manuali/supporto | Cantina | Pubblici e scaricabili | OK | P2 | OK |
| C. Apertura link invito | Studio invitato non loggato | Pagina pubblica invito presente lato codice | Non testato con token reale | P1 | Test end-to-end con invito reale |
| C. Login con email sbagliata | Studio | Codice blocca mismatch email su accept GET/POST | Messaggio registrazione meno esplicito | P1 | Uniformare messaggio con email attesa/usata |
| C. Login/registrazione email corretta | Studio | Codice mantiene token e accetta | Non testato con dati reali | P1 | Test end-to-end prima DNS |
| C. Accettazione invito | Studio | Crea/aggiorna `studio_clients`, marca used_at | Non testato con token reale | P1 | Test reale con due studi |
| C. Area Studio | Studio non loggato | `303` senza `Location` | Blocco accesso al login | P0 | Fix redirect globale |
| C. Workspace cantina | Studio | Permessi via `studio_clients` | Non testato con account reale | P1 | Test permessi view/edit/create |
| C. Permessi | Studio | `can_view/can_edit/can_create` usati | UX da verificare | P1 | Test con permessi diversi |
| C. Export | Studio | Link export in workspace | Non testato con account reale | P1 | Test con studio can_view/can_edit |
| D. Cantina invita studio | Cantina | Route POST presente, SMTP fallback previsto | Non testato per non creare dati | P1 | Test reale controllato |
| D. Cantina vede inviti in attesa | Cantina | UX aggiornata nel codice corrente/candidato: inviti in attesa chiari | Verificare deploy | P1 | Smoke con invito reale |
| D. Copia link invito | Cantina | Previsto in UX recente | Non testato con token reale | P1 | Test manuale browser |
| D. Studio accetta | Studio | Logica strict email presente | Non testato con token reale | P1 | Test completo |
| D. Cantina vede studio collegato | Cantina | Lista `studio_clients` presente | Non testato con dati reali | P1 | Test con accettazione reale |
| D. Modifica permessi | Cantina | POST set verifica owner/admin | Non testato per non modificare dati | P1 | Test in staging con dati test |
| D. Revoca accesso | Cantina | POST revoke verifica owner/admin | Non testato per non cancellare dati | P1 | Test in staging con dati test |
| D. Studio perde accesso | Studio | Atteso via assenza `studio_clients` | Non testato per non revocare dati | P1 | Test in staging |
| E. QR non esistente | Non loggato | `/e/qa-nonexistent...` `404` | OK | P2 | Messaggio piu umano opzionale |
| E. QR incompleto | Pubblico | Codice pubblico fa 404 se incompleto | Non testato con QR reale | P1 | Test DB con QR incompleto |
| E. Preview senza login | Non loggato | QR inesistente `404`; slug reale protetto soffrirebbe redirect 303 senza Location | Blocco login | P0 | Fix redirect globale |
| E. Preview QR altrui | Utente loggato | Codice ACL previsto: owner/studio can_view/admin | Non testato con account reale | P1 | Test con due cantine/studi |
| E. Invito scaduto/usato | Studio | Pagine dedicate presenti lato codice | Non testato con token reale | P2 | Test con token fixture |
| E. Password reset token non valido | Non loggato | `200`, messaggio chiaro | OK | P2 | OK |
| E. PayPal return incoerente | Non loggato | `303` senza `Location`; da loggato codice token-check candidato presente | Blocco login in sessione scaduta | P0/P1 | Fix redirect; test sandbox logged-in |
| E. Link PDF mancanti | Non loggato | Tutti i manuali richiesti `200` | OK | P2 | OK |

## 7. P0 da correggere prima del DNS pubblico

1. **Redirect login rotto per route protette**

   Evidenza:

   ```http
   GET /app/dashboard
   HTTP/1.1 303 See Other
   content-length: 15
   content-type: text/html; charset=utf-8
   # manca Location: /login?expired=1
   ```

   Impatto: un utente medio che apre una pagina protetta senza sessione puo' non arrivare al login. Questo impatta Cantina, Studio, preview protette e PayPal return con sessione scaduta.

   Fix consigliato: in `qrfacile_app/main.py`, per status `303/307/308` preservare `exc.headers` o lasciare passare i redirect. Esempio concettuale: `return Response(status_code=code, headers=exc.headers)` oppure una `RedirectResponse` se esiste `Location`.

2. **Verificare in deploy che `/studio/settings` sia presente**

   Lo scenario storico aveva link a `/studio/settings`. Se la route candidata non e' stata applicata all'ambiente, rimane P0 UX da menu Studio.

## 8. P1 consigliati prima del lancio commerciale

1. Applicare/verificare migrazione `password_reset_tokens` prima di promuovere il recupero password.
2. Test end-to-end invito Studio con email corretta e email sbagliata.
3. Test end-to-end Cantina invita Studio: invito in attesa, copia link, accettazione, collegamento visibile, modifica permessi, revoca.
4. Test PayPal sandbox con sessione valida, sessione scaduta e token/order mismatch.
5. Test preview ACL con due cantine e uno studio senza permesso.
6. Uniformare messaggi mismatch email tra accettazione invito e registrazione da invito.
7. Rendere piu' umano qualche errore tecnico (`Forbidden`, `QR not found`).
8. Verificare che la UX2 di `winery_settings_ui.py` sia effettivamente deployata: con zero studi non deve apparire "Gestisci studio collegato".

## 9. P2 evoluzioni future

1. Aggiungere azioni sicure per inviti: annulla invito, reinvia email, storico inviti.
2. Migliorare CTA acquisto da pubblico: "Accedi per acquistare".
3. Aggiungere micro-help contestuali nella compliance cantina.
4. Hardening: CSRF sui POST sensibili, cookie `Secure` sotto HTTPS, scadenza sessione server-side.
5. Dashboard studio: distinguere meglio "pubblica" da "prepara/export" quando lo studio non puo' pubblicare.

## 10. Giudizio finale: pubblicabile si/no

**No, non ancora per DNS pubblico.**

Motivo: il redirect login senza `Location` e' un P0 reale, verificato via HTTP. Dopo quel fix e un breve smoke test con account reali Cantina/Studio/Admin, la piattaforma puo' diventare pubblicabile con rischio residuo ragionevole.

## Smoke test eseguiti

```bash
curl -sS -L -o /tmp/qrf_home.html -w '%{http_code} %{url_effective}\n' http://192.168.1.139:8000/
curl -sS -L -o /tmp/qrf_pricing.html -w '%{http_code} %{url_effective}\n' http://192.168.1.139:8000/pricing
curl -sS -L -o /tmp/qrf_guide.html -w '%{http_code} %{url_effective}\n' http://192.168.1.139:8000/guide
curl -sS -L -o /tmp/qrf_login.html -w '%{http_code} %{url_effective}\n' http://192.168.1.139:8000/login
curl -sS -L -o /tmp/qrf_trust.html -w '%{http_code} %{url_effective}\n' http://192.168.1.139:8000/trust
curl -sS -L -o /tmp/qrf_support.html -w '%{http_code} %{url_effective}\n' http://192.168.1.139:8000/support
curl -sS -L -o /tmp/qrf_forgot.html -w '%{http_code} %{url_effective}\n' http://192.168.1.139:8000/forgot-password
curl -sS -L -o /tmp/qrf_reset_invalid.html -w '%{http_code} %{url_effective}\n' 'http://192.168.1.139:8000/reset-password?token=invalid-qa-token'
curl -sS -I http://192.168.1.139:8000/static/manuali/manuale_cantina.pdf
curl -sS -I http://192.168.1.139:8000/static/manuali/manuale_studio.pdf
curl -sS -I http://192.168.1.139:8000/static/manuali/manuale_qr_stampa.pdf
curl -sS -D - -o /dev/null http://192.168.1.139:8000/app/dashboard
curl -sS -D - -o /dev/null http://192.168.1.139:8000/studio/settings
```
