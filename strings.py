"""Telether localization (English / Italian).

Single source of user-facing strings. `tr(lang, key, **kw)` returns the string
for the given language ("en" or "it"), falling back to English then to the key.
"""

DEFAULT_LANG = "en"

HELP_EN = (
    "<b>Telether — terminal ↔ Telegram</b>\n\n"
    "Type a normal message and it is typed into the terminal followed by Enter.\n"
    "To launch Claude Code type <code>claude</code>, for Codex type <code>codex</code>.\n\n"
    "<b>Special keys</b>\n"
    "/enter /esc /tab /space /bs /del\n"
    "/up /down /left /right /home /end /pgup /pgdn\n"
    "/ctrl c  → send Ctrl+C (also z, d, l, ...)\n"
    "/cc  → double Ctrl+C (to exit Claude Code / Codex)\n\n"
    "<b>Scrolling</b>\n"
    "Use the 🔼 up / 🔽 down buttons under the screen, or /scrollup and /scrolldown.\n\n"
    "<b>Sessions</b>\n"
    "/new [name]  → new session   /sessions  → list   /use &lt;n&gt;  → switch\n"
    "/close [n]  → close   /rename &lt;name&gt;  → rename\n"
    "Tap a session button to switch; ➕ to create one.\n\n"
    "<b>Bridge commands</b>\n"
    "/type &lt;text&gt;  → type without pressing Enter\n"
    "/screen  → resend the current screen\n"
    "/clear  → clear the screen (Ctrl+L)\n"
    "/restart  → restart the terminal\n"
    "/kill  → send Ctrl+C to the process\n"
    "/size 80 30  → change size\n"
    "/lang it|en  → change language\n"
    "/status  → bridge status\n\n"
    "<b>Tips</b>\n"
    "• Unknown slash commands (e.g. <code>/model</code>) are sent as-is to the "
    "terminal, handy for Claude Code's own commands.\n"
    "• To send text starting with «/» literally, prefix it with <code>//</code> "
    "(e.g. <code>//help</code> → «/help»).\n"
)

HELP_IT = (
    "<b>Telether — terminale ↔ Telegram</b>\n\n"
    "Scrivi un messaggio normale e viene digitato nel terminale seguito da Invio.\n"
    "Per lanciare Claude Code scrivi <code>claude</code>, per Codex <code>codex</code>.\n\n"
    "<b>Tasti speciali</b>\n"
    "/enter /esc /tab /space /bs /del\n"
    "/up /down /left /right /home /end /pgup /pgdn\n"
    "/ctrl c  → invia Ctrl+C (anche z, d, l, ...)\n"
    "/cc  → doppio Ctrl+C (per uscire da Claude Code / Codex)\n\n"
    "<b>Scorrimento</b>\n"
    "Usa i pulsanti 🔼 su / 🔽 giù sotto lo schermo, oppure /su e /giu.\n\n"
    "<b>Sessioni</b>\n"
    "/new [nome]  → nuova   /sessions  → elenco   /use &lt;n&gt;  → cambia\n"
    "/close [n]  → chiudi   /rename &lt;nome&gt;  → rinomina\n"
    "Tocca il pulsante di una sessione per cambiarla; ➕ per crearne una.\n\n"
    "<b>Comandi del ponte</b>\n"
    "/type &lt;testo&gt;  → digita senza premere Invio\n"
    "/screen  → rimanda lo schermo attuale\n"
    "/clear  → pulisci lo schermo (Ctrl+L)\n"
    "/restart  → riavvia il terminale\n"
    "/kill  → invia Ctrl+C al processo\n"
    "/size 80 30  → cambia dimensioni\n"
    "/lang it|en  → cambia lingua\n"
    "/status  → stato del ponte\n\n"
    "<b>Trucchi</b>\n"
    "• I comandi slash sconosciuti (es. <code>/model</code>) vengono inviati "
    "così come sono al terminale, utile per i comandi interni di Claude Code.\n"
    "• Per inviare del testo che inizia con «/» senza interpretarlo, "
    "mettici <code>//</code> davanti (es. <code>//help</code> → «/help»).\n"
)

STRINGS = {
    "help": {"en": HELP_EN, "it": HELP_IT},
    "btn_up": {"en": "🔼 up", "it": "🔼 su"},
    "btn_down": {"en": "🔽 down", "it": "🔽 giù"},
    "btn_new": {"en": "➕ new session", "it": "➕ nuova sessione"},
    "empty_screen": {"en": "(empty screen)", "it": "(schermo vuoto)"},
    "proc_dead": {"en": "\n\n[process ended — use /restart]",
                  "it": "\n\n[processo terminato — usa /restart]"},
    "no_session": {"en": "<pre>(no session)</pre>", "it": "<pre>(nessuna sessione)</pre>"},
    "sess_default": {"en": "session {n}", "it": "sessione {n}"},
    "paired": {
        "en": "✅ Paired. This device now controls the terminal.\n\n",
        "it": "✅ Associazione completata. Questo dispositivo ora controlla il terminale.\n\n",
    },
    "unauthorized": {
        "en": "⛔ Not authorized. Your chat id is <code>{id}</code>.\n"
              "Add it to <code>allowed_chat_ids</code> in config.json and restart.",
        "it": "⛔ Non autorizzato. Il tuo chat id è <code>{id}</code>.\n"
              "Aggiungilo a <code>allowed_chat_ids</code> in config.json e riavvia.",
    },
    "new_created": {"en": "➕ New session: <b>{name}</b>", "it": "➕ Nuova sessione: <b>{name}</b>"},
    "sessions_header": {"en": "Sessions:", "it": "Sessioni:"},
    "sessions_hint": {"en": "\n\nUse the buttons or /use &lt;n&gt;.",
                      "it": "\n\nUsa i pulsanti o /use &lt;n&gt;."},
    "session_ended_tag": {"en": " (ended)", "it": " (terminata)"},
    "use_ok": {"en": "→ session <b>{name}</b>", "it": "→ sessione <b>{name}</b>"},
    "use_bad": {"en": "No such session.", "it": "Sessione inesistente."},
    "use_usage": {"en": "Usage: /use <n>  (see /sessions)", "it": "Uso: /use <n>  (vedi /sessions)"},
    "closed": {"en": "🗑️ Session <b>{name}</b> closed.", "it": "🗑️ Sessione <b>{name}</b> chiusa."},
    "close_usage": {"en": "Usage: /close [n]", "it": "Uso: /close [n]"},
    "rename_usage": {"en": "Usage: /rename <name>", "it": "Uso: /rename <nome>"},
    "ctrl_usage": {"en": "Usage: /ctrl <letter>  (e.g. /ctrl c)",
                   "it": "Uso: /ctrl <lettera>  (es. /ctrl c)"},
    "status": {
        "en": "Active session: <b>{name}</b> (id {id})\n"
              "Open sessions: {count}\n"
              "Shell: <code>{shell}</code>\n"
              "Size: {cols}x{rows}\n"
              "Process alive: {alive}\n"
              "Authorized chats: {chats}",
        "it": "Sessione attiva: <b>{name}</b> (id {id})\n"
              "Sessioni aperte: {count}\n"
              "Shell: <code>{shell}</code>\n"
              "Dimensioni: {cols}x{rows}\n"
              "Processo attivo: {alive}\n"
              "Chat autorizzate: {chats}",
    },
    "yes": {"en": "yes", "it": "sì"},
    "no": {"en": "no", "it": "no"},
    "no_active": {"en": "No active session.", "it": "Nessuna sessione attiva."},
    "restarted": {"en": "🔄 Session restarted: <code>{shell}</code>",
                  "it": "🔄 Sessione riavviata: <code>{shell}</code>"},
    "size_usage": {"en": "Usage: /size <cols> <rows>  (e.g. /size 80 30)",
                   "it": "Uso: /size <colonne> <righe>  (es. /size 80 30)"},
    "size_ok": {"en": "📐 Size: {cols}x{rows}", "it": "📐 Dimensioni: {cols}x{rows}"},
    "pair_info": {"en": "Chat id: <code>{id}</code> (already authorized).",
                  "it": "Chat id: <code>{id}</code> (già autorizzata)."},
    "started": {"en": "🟢 Telether started. Type /help for the guide.",
                "it": "🟢 Telether avviato. Scrivi /help per la guida."},
    "cb_new": {"en": "New: {name}", "it": "Nuova: {name}"},
    "cb_active": {"en": "Already active", "it": "Già attiva"},
    "cb_closed": {"en": "Session closed", "it": "Sessione chiusa"},
    "lang_set": {"en": "Language set to: {lang}", "it": "Lingua impostata: {lang}"},
    "lang_usage": {"en": "Usage: /lang it|en", "it": "Uso: /lang it|en"},
    # tray
    "tray_new": {"en": "➕ New session on PC", "it": "➕ Nuova sessione sul PC"},
    "tray_quit": {"en": "Quit", "it": "Esci"},
    "tray_no_token": {
        "en": "No bot token in config.json.\nOpen it, paste your @BotFather token "
              "into \"bot_token\", then restart.",
        "it": "Nessun token bot in config.json.\nAprilo e incolla il token di "
              "@BotFather in \"bot_token\", poi riavvia.",
    },
    # attach
    "attach_connected": {
        "en": "[connected to the session — press F12 to detach]",
        "it": "[collegato alla sessione — premi F12 per staccarti]",
    },
    "attach_detached": {
        "en": "[detached — the session keeps running]",
        "it": "[staccato — la sessione continua a girare]",
    },
    "attach_active_title": {"en": "active session", "it": "sessione attiva"},
    "attach_session_title": {"en": "session {n}", "it": "sessione {n}"},
    "attach_conn_fail": {"en": "Cannot connect to {host}:{port}.",
                         "it": "Impossibile collegarsi a {host}:{port}."},
    "attach_conn_hint": {"en": "Is Telether running? Detail: {err}",
                         "it": "Telether è in esecuzione? Dettaglio: {err}"},
}


def norm_lang(lang: str) -> str:
    lang = (lang or "").lower().strip()
    return lang if lang in ("en", "it") else DEFAULT_LANG


def tr(lang: str, key: str, **kw) -> str:
    entry = STRINGS.get(key)
    if not entry:
        return key
    text = entry.get(norm_lang(lang)) or entry.get("en") or key
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError):
            return text
    return text
