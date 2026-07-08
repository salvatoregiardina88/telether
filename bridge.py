#!/usr/bin/env python3
"""
Telether — control your Windows terminal from Telegram.

Spawns a real Windows console (ConPTY via pywinpty), emulates its screen with
pyte, and mirrors it into a Telegram chat. You type in Telegram, the keystrokes
go to the terminal; the terminal screen is shown back as a live, monospace
message. Designed to drive interactive TUIs like `claude` (Claude Code CLI),
`codex` (Codex CLI), ssh, etc. from your phone.

Run:  python bridge.py
See README.md for setup.
"""

from __future__ import annotations

import asyncio
import html
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import pyte
import winpty

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    Defaults,
    MessageHandler,
    filters,
)

import strings

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.json"

# Current UI language ("en" | "it"); set from config in build_application.
LANG = strings.DEFAULT_LANG


def t(key: str, **kw) -> str:
    return strings.tr(LANG, key, **kw)


DEFAULT_CONFIG = {
    "bot_token": "",
    "allowed_chat_ids": [],
    "language": "en",
    "shell": "powershell.exe -NoLogo",
    "cwd": "",
    "cols": 80,
    "rows": 30,
    "auto_enter": True,
    "render_interval": 1.5,
    "attach_port": 8765,
}

# --- Control-key tokens usable as /commands from Telegram -------------------
# token (without leading slash) -> bytes/str to write to the terminal.
CONTROL_KEYS = {
    "enter": "\r",
    "esc": "\x1b",
    "escape": "\x1b",
    "tab": "\t",
    "space": " ",
    "bs": "\x7f",
    "backspace": "\x7f",
    "del": "\x1b[3~",
    "delete": "\x1b[3~",
    "up": "\x1b[A",
    "down": "\x1b[B",
    "right": "\x1b[C",
    "left": "\x1b[D",
    "home": "\x1b[H",
    "end": "\x1b[F",
    "pgup": "\x1b[5~",
    "pgdn": "\x1b[6~",
    "pagedown": "\x1b[6~",
    "pageup": "\x1b[5~",
}

# Commands handled by the bridge itself (not forwarded to the terminal).
BRIDGE_COMMANDS = {
    "start", "help", "screen", "status", "restart", "kill",
    "size", "type", "ctrl", "pair", "clear",
}

class Terminal:
    """A ConPTY-backed shell whose screen is emulated with pyte."""

    def __init__(self, shell: str, cols: int, rows: int, cwd: str | None = None):
        self.shell = shell
        self.cols = cols
        self.rows = rows
        self.cwd = cwd or None
        self.lock = threading.Lock()
        # HistoryScreen keeps a scrollback buffer so we can page up/down.
        self.screen = pyte.HistoryScreen(cols, rows, history=3000, ratio=0.5)
        self.stream = pyte.Stream(self.screen)
        self.proc: winpty.PtyProcess | None = None
        self.alive = False
        self.version = 0  # bumped on every screen change / state change
        self._reader: threading.Thread | None = None
        # Called (in the reader thread) with each raw output chunk; used to
        # mirror the session to locally-attached PC clients.
        self.on_output = None

    def start(self):
        self.screen.reset()
        self.proc = winpty.PtyProcess.spawn(
            self.shell, cwd=self.cwd, dimensions=(self.rows, self.cols)
        )
        self.alive = True
        self.version += 1
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self):
        proc = self.proc
        while True:
            try:
                data = proc.read(65536)
            except (EOFError, OSError):
                break
            if data:
                with self.lock:
                    self.stream.feed(data)
                    self.version += 1
                cb = self.on_output
                if cb is not None:
                    cb(data)
            elif not proc.isalive():
                break
        self.alive = False
        self.version += 1

    def write(self, text: str):
        if self.proc is None:
            return
        try:
            self.proc.write(text)
        except (EOFError, OSError):
            self.alive = False
            self.version += 1

    def render(self) -> str:
        with self.lock:
            lines = [line.rstrip() for line in self.screen.display]
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)

    def snapshot(self) -> str:
        """VT snapshot for a freshly-attached local client: clears the window,
        redraws the current screen and puts the cursor where it really is."""
        with self.lock:
            lines = [line.rstrip() for line in self.screen.display]
            cy, cx = self.screen.cursor.y, self.screen.cursor.x
        last = len(lines) - 1
        while last > cy and not lines[last]:
            last -= 1
        body = "\r\n".join(lines[: last + 1])
        return "\x1b[2J\x1b[H" + body + f"\x1b[{cy + 1};{cx + 1}H"

    def scroll_up(self):
        with self.lock:
            self.screen.prev_page()
        self.version += 1

    def scroll_down(self):
        with self.lock:
            self.screen.next_page()
        self.version += 1

    def resize(self, cols: int, rows: int):
        self.cols, self.rows = cols, rows
        with self.lock:
            self.screen.resize(rows, cols)
        if self.proc is not None:
            try:
                self.proc.setwinsize(rows, cols)
            except (EOFError, OSError):
                pass
        self.version += 1

    def stop(self):
        if self.proc is not None:
            try:
                self.proc.terminate(force=True)
            except Exception:
                pass
        self.alive = False


@dataclass
class Session:
    id: int
    name: str
    term: Terminal
    attach_clients: set = field(default_factory=set)
    unread: bool = False          # background output not yet seen
    death_notified: bool = False
    seen_ver: int | None = None   # last screen version accounted for


@dataclass
class State:
    config: dict
    sessions: dict = field(default_factory=dict)   # id -> Session
    active_id: int | None = None
    next_id: int = 1
    primary_chat: int | None = None
    live_msg_id: int | None = None
    last_body: str = ""
    last_version: int = -1        # version of the active session last rendered
    last_kb_sig: tuple = ()       # signature of the last-sent keyboard
    want_new_message: bool = False
    allowed: set[int] = field(default_factory=set)
    loop: object | None = None
    render_task: object | None = None

    @property
    def active(self) -> "Session | None":
        if self.active_id is None:
            return None
        return self.sessions.get(self.active_id)


STATE: State | None = None


# --- Session management ------------------------------------------------------

def create_session(state: State, name: str | None = None) -> Session:
    sid = state.next_id
    state.next_id += 1
    cfg = state.config
    term = Terminal(cfg["shell"], int(cfg["cols"]), int(cfg["rows"]), cwd=resolve_cwd(cfg))
    sess = Session(id=sid, name=name or t("sess_default", n=sid), term=term)
    term.on_output = make_broadcaster(state, sess)
    term.start()
    state.sessions[sid] = sess
    state.active_id = sid
    return sess


def switch_active(state: State, sid: int) -> bool:
    if sid not in state.sessions:
        return False
    state.active_id = sid
    state.sessions[sid].unread = False
    state.last_version = -1        # force a re-render of the newly active screen
    state.want_new_message = True
    return True


def close_session(state: State, sid: int) -> bool:
    sess = state.sessions.pop(sid, None)
    if sess is None:
        return False
    sess.term.stop()
    for w in list(sess.attach_clients):
        try:
            w.close()
        except Exception:
            pass
    if state.active_id == sid:
        if state.sessions:
            state.active_id = next(iter(state.sessions))
            state.sessions[state.active_id].unread = False
        else:
            create_session(state)      # never leave the user with zero sessions
        state.last_version = -1
        state.want_new_message = True
    return True


# --- Config -----------------------------------------------------------------

def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            print(f"[!] config.json non valido: {exc}", file=sys.stderr)
    return cfg


def save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


# --- Telegram rendering -----------------------------------------------------

def build_body(state: State) -> str:
    sess = state.active
    if sess is None:
        return t("no_session")
    text = sess.term.render()
    if not text.strip():
        text = t("empty_screen")
    if not sess.term.alive:
        text += t("proc_dead")
    header = f"▶ {html.escape(sess.name)}\n"
    body = header + "<pre>" + html.escape(text) + "</pre>"
    if len(body) > 4096:
        # keep the tail, which is where the action is
        clipped = text[-3700:]
        body = header + "<pre>" + html.escape(clipped) + "</pre>"
    return body


def build_keyboard(state: State) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(t("btn_up"), callback_data="scrollup"),
        InlineKeyboardButton(t("btn_down"), callback_data="scrolldown"),
    ]]
    # one button per session (max ~3 per row), active marked with ▶, unread •
    session_buttons = []
    for sid, sess in state.sessions.items():
        label = sess.name
        if sid == state.active_id:
            label = "▶ " + label
        elif sess.unread:
            label = label + " •"
        session_buttons.append(InlineKeyboardButton(label, callback_data=f"use:{sid}"))
    for i in range(0, len(session_buttons), 3):
        rows.append(session_buttons[i:i + 3])
    rows.append([InlineKeyboardButton(t("btn_new"), callback_data="new")])
    return InlineKeyboardMarkup(rows)


def keyboard_signature(state: State) -> tuple:
    return (
        state.active_id,
        tuple((sid, s.name, s.unread) for sid, s in state.sessions.items()),
    )


async def push_screen(bot, state: State, force_new: bool = False):
    if state.primary_chat is None:
        return
    body = build_body(state)
    kb = build_keyboard(state)
    state.last_kb_sig = keyboard_signature(state)
    try:
        if force_new or state.live_msg_id is None:
            msg = await bot.send_message(
                state.primary_chat, body, parse_mode=ParseMode.HTML, reply_markup=kb,
            )
            state.live_msg_id = msg.message_id
            state.last_body = body
        else:
            if body == state.last_body:
                return
            await bot.edit_message_text(
                body, chat_id=state.primary_chat, message_id=state.live_msg_id,
                parse_mode=ParseMode.HTML, reply_markup=kb,
            )
            state.last_body = body
    except BadRequest as exc:
        msg_l = str(exc).lower()
        if "not modified" in msg_l:
            state.last_body = body
            return
        # message too old / deleted -> post a fresh one
        try:
            msg = await bot.send_message(
                state.primary_chat, body, parse_mode=ParseMode.HTML, reply_markup=kb,
            )
            state.live_msg_id = msg.message_id
            state.last_body = body
        except TelegramError as exc2:
            print(f"[!] push fallito: {exc2}", file=sys.stderr)
    except RetryAfter as exc:
        await asyncio.sleep(exc.retry_after + 1)
    except Forbidden:
        print("[!] Bot bloccato dall'utente.", file=sys.stderr)
    except TelegramError as exc:
        print(f"[!] errore Telegram: {exc}", file=sys.stderr)


async def refresh_keyboard(bot, state: State):
    """Update only the inline keyboard (e.g. unread dots) without touching text."""
    if state.primary_chat is None or state.live_msg_id is None:
        return
    state.last_kb_sig = keyboard_signature(state)
    try:
        await bot.edit_message_reply_markup(
            chat_id=state.primary_chat, message_id=state.live_msg_id,
            reply_markup=build_keyboard(state),
        )
    except (BadRequest, TelegramError):
        pass


async def render_loop(app: Application):
    state = STATE
    interval = float(state.config.get("render_interval", 1.5))
    while True:
        await asyncio.sleep(interval)
        if state.primary_chat is None:
            continue
        sess = state.active
        if sess is None:
            continue
        # mark background sessions that produced new output as unread
        for s in state.sessions.values():
            if s is sess:
                continue
            v = s.term.version
            if s.seen_ver is None:
                s.seen_ver = v
            elif v != s.seen_ver:
                s.seen_ver = v
                if s.term.alive:
                    s.unread = True
        ver = sess.term.version
        sess.seen_ver = ver          # keep active baseline current
        changed = ver != state.last_version
        if changed or state.want_new_message:
            force_new = state.want_new_message
            state.want_new_message = False
            await push_screen(app.bot, state, force_new=force_new)
            state.last_version = ver
        elif keyboard_signature(state) != state.last_kb_sig:
            await refresh_keyboard(app.bot, state)
        if not sess.term.alive and not sess.death_notified:
            sess.death_notified = True
            await push_screen(app.bot, state, force_new=True)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = STATE
    query = update.callback_query
    if query is None:
        return
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id not in state.allowed:
        try:
            await query.answer("Non autorizzato")
        except TelegramError:
            pass
        return
    state.primary_chat = chat_id
    data = query.data or ""
    note = None
    is_scroll = data in ("scrollup", "scrolldown")

    if data == "scrollup":
        if state.active:
            state.active.term.scroll_up()
    elif data == "scrolldown":
        if state.active:
            state.active.term.scroll_down()
    elif data == "new":
        sess = create_session(state)
        note = t("cb_new", name=sess.name)
    elif data.startswith("use:"):
        try:
            sid = int(data.split(":", 1)[1])
        except ValueError:
            sid = -1
        if sid == state.active_id:
            note = t("cb_active")
        elif switch_active(state, sid):
            note = f"→ {state.sessions[sid].name}"
        else:
            note = t("cb_closed")

    try:
        await query.answer(note or "")
    except TelegramError:
        pass

    if is_scroll:
        # scroll: aggiorna in-place il messaggio su cui si è premuto
        if query.message is not None:
            state.live_msg_id = query.message.message_id
            state.last_body = ""
        await push_screen(context.bot, state)
    else:
        # cambio/creazione sessione: nuovo messaggio in fondo con la sessione scelta
        state.want_new_message = False
        await push_screen(context.bot, state, force_new=True)
        if state.active:
            state.last_version = state.active.term.version


# --- Authorization ----------------------------------------------------------

def is_authorized(state: State, chat_id: int) -> bool:
    return chat_id in state.allowed


async def try_pair(state: State, chat_id: int) -> bool:
    """In pairing mode (no allowed chats yet) adopt the first chat."""
    if state.allowed:
        return False
    state.allowed.add(chat_id)
    state.config["allowed_chat_ids"] = sorted(state.allowed)
    save_config(state.config)
    print(f"[+] Chat {chat_id} associata e salvata in config.json")
    return True


# --- Message handling -------------------------------------------------------

async def dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = STATE
    msg = update.effective_message
    if msg is None or msg.text is None:
        return
    chat_id = update.effective_chat.id
    text = msg.text

    if not is_authorized(state, chat_id):
        paired = await try_pair(state, chat_id)
        if paired:
            state.primary_chat = chat_id
            await context.bot.send_message(
                chat_id,
                t("paired") + t("help"),
                parse_mode=ParseMode.HTML,
            )
            state.want_new_message = True
            return
        await context.bot.send_message(
            chat_id,
            t("unauthorized", id=chat_id),
            parse_mode=ParseMode.HTML,
        )
        return

    state.primary_chat = chat_id

    # Literal escape: "//foo" -> send "/foo" + Enter
    if text.startswith("//"):
        await send_text_line(state, text[1:])
        return

    if text.startswith("/"):
        await handle_command(update, context, state, text)
        return

    # Plain text -> type it into the terminal.
    await send_text_line(state, text)


def submit_sequence(text: str) -> str:
    """Bytes to type `text` into the terminal and submit it with Enter.

    If the message spans multiple lines, the line breaks are sent inside a
    *bracketed paste* (ESC[200~ … ESC[201~) so that TUIs like Claude Code and
    Codex treat them as soft line breaks in the input, NOT as separate Enters.
    A final CR then submits the whole message once. Single-line messages are
    just `text` + CR.
    """
    if "\n" in text or "\r" in text:
        body = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r")
        return "\x1b[200~" + body + "\x1b[201~" + "\r"
    return text + "\r"


async def send_text_line(state: State, text: str):
    sess = state.active
    if sess is None:
        return
    if state.config.get("auto_enter", True):
        sess.term.write(submit_sequence(text))
    else:
        sess.term.write(text)
    state.want_new_message = True


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE, state: State, text: str):
    parts = text[1:].split()
    if not parts:
        return
    raw = parts[0]
    # strip @botname suffix used in groups
    cmd = raw.split("@", 1)[0].lower()
    args = parts[1:]
    arg_str = text[1:].partition(" ")[2]
    chat_id = update.effective_chat.id

    sess = state.active
    term = sess.term if sess else None

    # --- pure control keys ---
    if cmd in CONTROL_KEYS:
        if term:
            term.write(CONTROL_KEYS[cmd])
        return

    # --- bridge commands ---
    if cmd in ("start", "help"):
        await context.bot.send_message(chat_id, t("help"), parse_mode=ParseMode.HTML)
        state.want_new_message = True
        return

    if cmd in ("lang", "language", "lingua"):
        new_lang = args[0].lower() if args else ""
        if new_lang not in ("en", "it"):
            await context.bot.send_message(chat_id, t("lang_usage"))
            return
        set_language(state, new_lang)
        try:
            await context.bot.set_my_commands(localized_commands())
        except TelegramError:
            pass
        await context.bot.send_message(chat_id, t("lang_set", lang=new_lang))
        state.last_version = -1
        state.want_new_message = True
        return

    # --- sessioni multiple ---
    if cmd in ("new", "nuova", "n"):
        new_sess = create_session(state)
        if arg_str.strip():
            new_sess.name = arg_str.strip()[:24]
        state.last_version = -1
        state.want_new_message = True
        await context.bot.send_message(chat_id, t("new_created", name=html.escape(new_sess.name)), parse_mode=ParseMode.HTML)
        return

    if cmd in ("sessions", "ls", "sessioni"):
        lines = []
        for sid, s in state.sessions.items():
            mark = "▶" if sid == state.active_id else ("•" if s.unread else " ")
            ended = "" if s.term.alive else t("session_ended_tag")
            lines.append(f"{mark} <code>{sid}</code> {html.escape(s.name)}{ended}")
        body = t("sessions_header") + "\n" + "\n".join(lines) + t("sessions_hint")
        await context.bot.send_message(chat_id, body, parse_mode=ParseMode.HTML)
        return

    if cmd in ("use", "switch", "sw"):
        try:
            sid = int(args[0])
        except (ValueError, IndexError):
            await context.bot.send_message(chat_id, t("use_usage"))
            return
        if switch_active(state, sid):
            await context.bot.send_message(chat_id, t("use_ok", name=html.escape(state.sessions[sid].name)), parse_mode=ParseMode.HTML)
        else:
            await context.bot.send_message(chat_id, t("use_bad"))
        return

    if cmd in ("close", "chiudi", "kill_session"):
        sid = state.active_id
        if args:
            try:
                sid = int(args[0])
            except ValueError:
                await context.bot.send_message(chat_id, t("close_usage"))
                return
        name = state.sessions[sid].name if sid in state.sessions else str(sid)
        if close_session(state, sid):
            state.last_version = -1
            state.want_new_message = True
            await context.bot.send_message(chat_id, t("closed", name=html.escape(name)), parse_mode=ParseMode.HTML)
        else:
            await context.bot.send_message(chat_id, t("use_bad"))
        return

    if cmd in ("rename", "rinomina"):
        if not arg_str.strip():
            await context.bot.send_message(chat_id, t("rename_usage"))
            return
        if sess:
            sess.name = arg_str.strip()[:24]
            state.last_version = -1
            await push_screen(context.bot, state)
        return

    if cmd == "ctrl":
        if not args:
            await context.bot.send_message(chat_id, t("ctrl_usage"))
            return
        ch = args[0].strip().lower()[:1]
        if term and ch.isalpha():
            term.write(chr(ord(ch.upper()) - 64))
        elif term and ch == "[":
            term.write("\x1b")
        return

    if cmd == "clear":
        if term:
            term.write("\x0c")  # Ctrl+L
        return

    # doppio Ctrl+C a mezzo secondo di distanza: chiude Claude Code, Codex e
    # altri TUI che richiedono due Ctrl+C per uscire.
    if cmd in ("cc", "ctrlcc", "quit", "qq"):
        if term:
            term.write("\x03")
            await asyncio.sleep(0.5)
            term.write("\x03")
        state.want_new_message = True
        return

    # scorrimento dello storico (scrollback) del terminale
    if cmd in ("scrollup", "su", "pgu"):
        if term:
            term.scroll_up()
        await push_screen(context.bot, state)
        return
    if cmd in ("scrolldown", "giu", "pgd"):
        if term:
            term.scroll_down()
        await push_screen(context.bot, state)
        return

    if cmd == "type":
        if term and arg_str:
            term.write(arg_str)
        return

    if cmd == "screen":
        await push_screen(context.bot, state, force_new=True)
        return

    if cmd == "status":
        if term is None:
            await context.bot.send_message(chat_id, t("no_active"))
            return
        await context.bot.send_message(
            chat_id,
            t("status",
              name=html.escape(sess.name), id=sess.id, count=len(state.sessions),
              shell=html.escape(term.shell), cols=term.cols, rows=term.rows,
              alive=t("yes") if term.alive else t("no"), chats=sorted(state.allowed)),
            parse_mode=ParseMode.HTML,
        )
        return

    if cmd == "kill":
        if term:
            term.write("\x03")
        state.want_new_message = True
        return

    if cmd == "restart":
        if sess is None:
            return
        new_shell = arg_str.strip() or state.config.get("shell")
        sess.term.stop()
        await asyncio.sleep(0.3)
        sess.term = Terminal(
            new_shell, state.config["cols"], state.config["rows"], cwd=resolve_cwd(state.config)
        )
        sess.term.on_output = make_broadcaster(state, sess)
        sess.term.start()
        sess.death_notified = False
        sess.seen_ver = None
        state.last_version = -1
        state.want_new_message = True
        await context.bot.send_message(chat_id, t("restarted", shell=html.escape(new_shell)), parse_mode=ParseMode.HTML)
        return

    if cmd == "size":
        try:
            if len(args) == 1 and "x" in args[0].lower():
                w, h = args[0].lower().split("x")
            else:
                w, h = args[0], args[1]
            cols, rows = int(w), int(h)
            cols = max(20, min(cols, 200))
            rows = max(10, min(rows, 60))
        except (ValueError, IndexError):
            await context.bot.send_message(chat_id, t("size_usage"))
            return
        state.config["cols"], state.config["rows"] = cols, rows
        save_config(state.config)
        for s in state.sessions.values():
            s.term.resize(cols, rows)
        await context.bot.send_message(chat_id, t("size_ok", cols=cols, rows=rows))
        state.want_new_message = True
        return

    if cmd == "pair":
        await context.bot.send_message(
            chat_id,
            t("pair_info", id=chat_id),
            parse_mode=ParseMode.HTML,
        )
        return

    # --- unknown slash command: forward literally to the terminal ---
    # (so Claude Code's /model, /clear, /compact, etc. work)
    await send_text_line(state, text)


# --- Local attach server ----------------------------------------------------
# Lets you sit at the PC and open the SAME live session in a native terminal
# window (full colour, TUIs work), while Telegram keeps controlling it too.

def make_broadcaster(state: State, session: "Session"):
    """Thread-safe callback that fans one session's raw output to its clients."""
    def _cb(data: str):
        loop = state.loop
        if loop is None or not session.attach_clients:
            return
        try:
            loop.call_soon_threadsafe(_broadcast_now, session, data)
        except RuntimeError:
            pass
    return _cb


def _broadcast_now(session: "Session", data: str):
    if not session.attach_clients:
        return
    raw = data.encode("utf-8", "replace")
    for writer in list(session.attach_clients):
        try:
            writer.write(raw)
        except Exception:
            session.attach_clients.discard(writer)


async def handle_attach_client(state: State, reader, writer):
    peer = writer.get_extra_info("peername")
    # Handshake: first line is "ATTACH <id|active>\n". Falls back to active.
    session = state.active
    try:
        line = await asyncio.wait_for(reader.readline(), timeout=2)
        token = line.decode("utf-8", "ignore").strip().split()
        if len(token) >= 2 and token[0].upper() == "ATTACH" and token[1] != "active":
            session = state.sessions.get(int(token[1]), session)
    except (asyncio.TimeoutError, ValueError, ConnectionError):
        pass
    if session is None:
        try:
            writer.close()
        except Exception:
            pass
        return
    session.attach_clients.add(writer)
    print(f"[+] Local client attached to '{session.name}': {peer}")
    try:
        writer.write(session.term.snapshot().encode("utf-8", "replace"))
        await writer.drain()
    except Exception:
        pass
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            session.term.write(data.decode("utf-8", "ignore"))
    except (ConnectionError, asyncio.IncompleteReadError):
        pass
    finally:
        session.attach_clients.discard(writer)
        try:
            writer.close()
        except Exception:
            pass
        print(f"[+] Local client detached from '{session.name}': {peer}")


async def start_attach_server(state: State):
    port = int(state.config.get("attach_port", 0) or 0)
    if not port:
        return
    try:
        await asyncio.start_server(
            lambda r, w: handle_attach_client(state, r, w), "127.0.0.1", port
        )
        print(f"[+] Attach server on 127.0.0.1:{port} — run attach.bat to connect")
    except OSError as exc:
        print(f"[!] Attach server not started: {exc}", file=sys.stderr)


# --- Startup ----------------------------------------------------------------

def localized_commands() -> list:
    if LANG == "it":
        pairs = [
            ("help", "Guida ai comandi"),
            ("screen", "Rimanda lo schermo attuale"),
            ("cc", "Doppio Ctrl+C (esci da Claude/Codex)"),
            ("su", "Scorri lo storico verso l'alto"),
            ("giu", "Scorri lo storico verso il basso"),
            ("new", "Nuova sessione"),
            ("sessions", "Elenca le sessioni"),
            ("use", "Passa alla sessione <n>"),
            ("close", "Chiudi la sessione"),
            ("restart", "Riavvia il terminale"),
            ("kill", "Invia Ctrl+C al processo"),
            ("lang", "Cambia lingua (it/en)"),
            ("status", "Stato del ponte"),
        ]
    else:
        pairs = [
            ("help", "Command guide"),
            ("screen", "Resend the current screen"),
            ("cc", "Double Ctrl+C (exit Claude/Codex)"),
            ("scrollup", "Scroll history up"),
            ("scrolldown", "Scroll history down"),
            ("new", "New session"),
            ("sessions", "List sessions"),
            ("use", "Switch to session <n>"),
            ("close", "Close the session"),
            ("restart", "Restart the terminal"),
            ("kill", "Send Ctrl+C to the process"),
            ("lang", "Change language (it/en)"),
            ("status", "Bridge status"),
        ]
    return [BotCommand(c, d) for c, d in pairs]


async def on_startup(app: Application):
    state = STATE
    state.loop = asyncio.get_running_loop()
    if not state.sessions:
        create_session(state)   # -> "session 1" / "sessione 1"
    await start_attach_server(state)
    try:
        await app.bot.set_my_commands(localized_commands())
    except TelegramError:
        pass
    state.render_task = asyncio.create_task(render_loop(app))
    if state.allowed:
        for chat_id in list(state.allowed):
            try:
                await app.bot.send_message(chat_id, t("started"))
                state.primary_chat = chat_id
            except TelegramError:
                pass
    print("[+] Bot started. Waiting for Telegram messages...")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    from telegram.error import Conflict
    err = context.error
    if isinstance(err, Conflict):
        print("[!] Another instance of the bot is already running with this token. "
              "Close the other start.bat windows and restart.", file=sys.stderr)
    else:
        print(f"[!] Telegram error: {err}", file=sys.stderr)


def obtain_token(cfg: dict) -> str:
    token = cfg.get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    token = token.strip()
    if not token and sys.stdin and sys.stdin.isatty():
        print("No bot token found.")
        print("Create one with @BotFather on Telegram (/newbot) and paste it here.")
        token = input("Telegram bot token: ").strip()
        if token:
            cfg["bot_token"] = token
            save_config(cfg)
    return token


def resolve_cwd(cfg: dict) -> str:
    return cfg.get("cwd") or os.path.expanduser("~")


def set_language(state: State, lang: str):
    global LANG
    LANG = strings.norm_lang(lang)
    state.config["language"] = LANG
    save_config(state.config)


def build_application(cfg: dict, token: str) -> Application:
    """Create the STATE + Telegram Application. Shared by CLI and tray app.
    The first session is spawned in on_startup (needs the running loop)."""
    global STATE, LANG
    LANG = strings.norm_lang(cfg.get("language"))
    STATE = State(config=cfg, allowed=set(cfg.get("allowed_chat_ids", [])))
    # disable_notification: nessun suono/notifica su telefono e PC per ogni
    # aggiornamento dello schermo.
    app = (
        Application.builder()
        .token(token)
        .defaults(Defaults(disable_notification=True))
        .post_init(on_startup)
        .build()
    )
    app.add_handler(MessageHandler(filters.TEXT, dispatch))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_error_handler(on_error)
    return app


def main():
    cfg = load_config()
    if not CONFIG_PATH.exists():
        save_config(cfg)
    token = obtain_token(cfg)
    if not token:
        print("[!] No token. Set 'bot_token' in config.json or the "
              "TELEGRAM_BOT_TOKEN environment variable, then restart.", file=sys.stderr)
        sys.exit(1)

    app = build_application(cfg, token)

    if not STATE.allowed:
        print("[i] No authorized chat: pairing mode active.")
        print("    The first person to message the bot will be paired automatically.")

    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    finally:
        if STATE:
            for s in STATE.sessions.values():
                s.term.stop()


if __name__ == "__main__":
    main()
