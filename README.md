# cinemacity-watchdog

Hlídá rozpis [Cinema City](https://www.cinemacity.cz) a když přibude nový termín
**Duny v IMAXu** (prosinec 2026), založí v tomhle repu issue a **přiřadí ho vlastníkovi repa**.
GitHub z něj pošle e-mail i push do mobilní appky.

Na přiřazení záleží: e-mail chodí ve výchozím nastavení jen u „Participating"
notifikací (přiřazení, zmínky, odpovědi). Pouhé sledování repa („Watching")
dává jen web/mobile notifikaci — e-mail je pro něj v Settings → Notifications
vypnutý, dokud si ho člověk nezapne.

Běží v GitHub Actions, takže funguje i když je počítač vypnutý.

## Jak to funguje

- Workflow [`.github/workflows/watch.yml`](.github/workflows/watch.yml) běží
  **každou půlhodinu** (v :08, :38, :21, :51 — mimo špičky, kdy GitHub cron nejvíc
  zahazuje běhy). Repo je veřejné, takže minuty Actions jsou zdarma bez limitu.
- [`watch.py`](watch.py) stáhne rozpis z veřejného JSON API cinemacity.cz
  (`/cz/data-api-service/v1/quickbook/10101/…`) — bez klíče, bez přihlášení.
- Seznam už viděných představení drží v [`state/seen.json`](state/seen.json),
  který si workflow po každém běhu commitne zpátky. Hlásí se tedy jen přírůstky.
- Nová představení → issue s časem, sálem, příznaky (70mm / titulky / vyprodáno)
  a přímým odkazem na nákup vstupenky. Hlásí se i termíny, které z rozpisu
  **zmizely** (zrušené projekce).
- Issue se **hned po založení zavírá**. Slouží jen jako doručovací kanál pro
  e-mail, který GitHub pošle už při jeho vzniku — seznam otevřených issues tak
  zůstává prázdný a nic není potřeba uklízet ručně. Obsah zůstává čitelný mezi
  zavřenými.
- Časy se počítají v zóně kina (`Europe/Prague`), ne v UTC runneru. Bez toho
  by projekce, která právě doběhla, vypadala jako budoucí a při zmizení
  z rozpisu by se falešně nahlásila jako zrušená.

Jeden běh je ~45 HTTP dotazů a trvá ~20 sekund.

## Co přesně se hlídá

Představení, kde **název filmu** obsahuje `dun` (odpovídá českému „Duna: část třetí“ i anglickému „Dune“) **a** **název sálu** obsahuje
`imax`. Aktuálně tomu odpovídá **Praha Flora**, sál
`IMAX VOLVO` (kde Duna startuje v prosinci 2026).

Aby se netahal celý rozpis všech třinácti kin, hledá se dvoufázově: nejdřív se
zjistí, která kina vůbec mají IMAX sál (jedna sonda na nejbližší hrací den plus
nápověda z API přes atribut `70-mm`), a do hloubky se projdou jen ta. Kdyby
IMAX přibyl v jiném kině, chytí se to samo.

Chování jde změnit proměnnými prostředí ve workflow nebo lokálně:

| Proměnná | Výchozí | Význam |
| --- | --- | --- |
| `FILM_PATTERN` | `dun` | podřetězec názvu filmu (`dun` nebo `dune`, case-insensitive) |
| `AUDITORIUM_PATTERN` | `imax` | podřetězec názvu sálu (nebo prázdné `""` pro všechny sály) |
| `MIN_AVAILABILITY_RATIO` | `0.50` | hlásit jen představení s **více než 50 % volných míst** (zajišťuje volné nejlepší řady) |
| `HORIZON_DAYS` | `180` | jak daleko dopředu se ptát (180 dní pokrývá prosinec 2026) |
| `HINT_ATTR` | `70-mm` | atribut pro levné dohledání kandidátských kin |
| `REQUEST_DELAY` | `0.25` | pauza mezi dotazy na API (s) |

Hlídat cokoli jiného (třeba `FILM_PATTERN=dune`, `AUDITORIUM_PATTERN=4dx`) tedy
znamená přepsat dvě proměnné a smazat `state/seen.json`.

## Chci to hlídat taky (fork)

Watchdog nepotřebuje žádné tokeny ani secrets — API Cinema City je veřejné
a na zakládání issues stačí vestavěný `GITHUB_TOKEN`. Rozjedeš ho takhle:

1. **Forkni** si tohle repo.
2. **Settings → General → Features → zaškrtni `Issues`.** Forky mají issues
   vypnuté a bez nich by watchdog neměl kudy hlásit.
3. **Actions → „I understand my workflows, go ahead and enable them".**
   GitHub v forcích naplánované workflows nespouští, dokud je nepovolíš.
4. Hotovo. Issues se zakládají a přiřazují tobě, protože workflow používá
   `${{ github.repository_owner }}` — nic přepisovat nemusíš.

Stav v `state/seen.json` se forkne s sebou, takže tě to nezasype aktuálním
rozpisem a ozve se až s prvním novým termínem. Chceš-li hned vidět, co se
hraje teď, spusť workflow ručně s `force_report`.

Hlídat jiný film než Odysseu: přepiš `FILM_PATTERN` (a případně
`AUDITORIUM_PATTERN`) ve workflow a smaž obsah `state/seen.json`.

## Ruční spuštění

**Actions → Cinema City watchdog → Run workflow**. Zaškrtnutí *force_report*
nahlásí všechny aktuální termíny, i ty už známé — hodí se na ověření, že to žije,
nebo jako „ukaž mi, co teď hrajou“.

```bash
gh workflow run watch.yml --repo TarkDetrius/cinemacity-watchdog -f force_report=true
```

## Lokální spuštění

Čistý Python 3, žádné externí knihovny ani závislosti:

**Windows (PowerShell):**
```powershell
# Standardní kontrola
python watch.py --state state/seen.json

# Výpis všech nalezených termínů (i už známých)
python watch.py --force-report

# Sledování jiného filmu / všech sálů:
$env:FILM_PATTERN = "dun"
$env:AUDITORIUM_PATTERN = ""  # všechna kina a všechny sály
python watch.py --force-report
```

**Linux / macOS (Bash):**
```bash
python3 watch.py --state state/seen.json
python3 watch.py --force-report
```

Užitečné přepínače:
- `--force-report`: vypíše všechna nalezená představení bez ohledu na stav.
- `--seed`: jen zapíše aktuální stav do JSON souboru a nic nehlásí.

## Notifikace do mobilu

Máš tři možnosti, jak dostávat okamžitá upozornění na telefon:

### 1. Aplikace GitHub Mobile (výchozí, bez další konfigurace)
- Stáhni si appku **GitHub** (iOS / Android) a přihlas se.
- Protože workflow vytváří issue a přiřazuje ho přímo tobě, GitHub ti automaticky pošle **push notifikaci na zamknutou obrazovku** a e-mail.

### 2. ntfy.sh (okamžitý push bez registrace — doporučeno)
- Stáhni si zdarma aplikaci **ntfy** (iOS / Android).
- V appce klikni na `+` a přidej libovolné téma, např. `duna-imax-watchdog-mojejmeno`.
- Ve forku na GitHubu jdi do **Settings → Secrets and variables → Actions** a přidej secret `NTFY_TOPIC` s názvem tvého tématu.
- Při každém novém termínu ti přijde hlasitá push notifikace s přímým odkazem na nákup!

### 3. Telegram Bot
- Vytvoř si bota přes `@BotFather` a získej `TELEGRAM_BOT_TOKEN`.
- Zjisti své ID přes `@userinfobot` (`TELEGRAM_CHAT_ID`).
- Ulož je do GitHub Secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).

## Údržba

- **Kvóta Actions:** repo je záměrně veřejné — u veřejných repozitářů jsou minuty
  GitHub Actions zdarma bez limitu.
- **Až Duna dohraje:** watchdog přestane hlásit. Buď workflow vypni v záložce Actions,
  nebo přepiš `FILM_PATTERN` na další film.
