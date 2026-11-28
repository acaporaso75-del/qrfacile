# QRFacile Compliance Framework 2026

## Scopo
Questo documento definisce il programma minimo di conformità per QRFacile rispetto a GDPR, ePrivacy/cookie, normativa e-label vino, accessibilità digitale e AI Act.

## Principi
- privacy by design e by default;
- minimizzazione dei dati;
- separazione tra contenuto normativo e marketing;
- approvazione umana per contenuti sensibili;
- tracciabilità delle modifiche;
- sicurezza, continuità e ripristino;
- documentazione verificabile.

## Ruoli privacy
Prima del rilascio commerciale definitivo deve essere formalizzato, per ciascun trattamento, se Enolab opera come:
- titolare autonomo;
- responsabile del trattamento ex art. 28 GDPR;
- contitolare.

Per i trattamenti svolti per conto delle cantine deve essere predisposto un DPA con istruzioni, misure di sicurezza, sub-responsabili, assistenza agli interessati, data breach, restituzione/cancellazione dei dati e audit.

## Obblighi tecnici prioritari
1. inventario trattamenti e dati;
2. registro dei trattamenti;
3. retention numerica per categoria;
4. registro sub-responsabili;
5. procedura data breach;
6. audit log amministrativo;
7. MFA per amministratori;
8. backup e restore testato;
9. export e cancellazione account;
10. registro versioni e accettazioni dei documenti legali.

## E-label vino
Le pagine usate per ingredienti e dichiarazione nutrizionale devono:
- evitare cookie non necessari;
- evitare analytics di terze parti, pixel, fingerprinting e profilazione;
- non raccogliere dati personali del visitatore salvo stretta necessità tecnica e base giuridica;
- non ospitare informazioni commerciali o promozionali nella stessa sezione normativa;
- mantenere allergeni e informazioni obbligatorie secondo la disciplina applicabile;
- essere disponibili e leggibili per l'intero ciclo di vita commerciale del prodotto.

## Accessibilità
Le interfacce e le pagine pubbliche devono essere sottoposte ad audit su:
- navigazione tastiera;
- focus visibile;
- contrasto;
- semantic HTML;
- etichette form;
- errori comprensibili;
- zoom e responsive;
- screen reader;
- testi alternativi;
- accessibilità dei documenti scaricabili.

## AI
Qualunque funzione AI deve rispettare la policy dedicata in `AI_POLICY.md`.

## Deliverable applicativi
- pagina pubblica AI Policy;
- tabella `legal_acceptances`;
- tabella `audit_log`;
- configurazione retention centralizzata;
- pannello admin compliance;
- test anti-tracking sulle e-label;
- checklist di approvazione umana;
- registro fornitori AI e sub-responsabili.

## Stato
Questo documento è un framework tecnico-organizzativo e non sostituisce la validazione finale di un avvocato o DPO sui rapporti contrattuali reali.