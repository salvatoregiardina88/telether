#!/usr/bin/env python3
"""
Telether — aggancia dal PC la stessa sessione controllata da Telegram.

Apre la sessione condivisa in questa finestra di terminale, a colori pieni e con
i TUI funzionanti (Claude Code, Codex, ecc.). Telegram continua a controllarla in
parallelo: quello che digiti qui e quello che arriva da Telegram finiscono nella
stessa identica sessione.

Uso:   python attach.py [id_sessione] [nome]
       (la porta viene letta da config.json, altrimenti 8765)

Per staccarti premi F12 o chiudi la finestra — la sessione continua a girare.
"""

import ctypes
import json
import msvcrt
import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import strings

HOST = "127.0.0.1"
DETACH_CHARS = ("\x1d",)      # Ctrl+]  (tastiere US)
DETACH_FKEYS = ("\x86", "\x88")  # F12 (\x00\x86) / alcune tastiere lo mandano diverso

# Sequenze inviate dai tasti speciali di Windows (prefisso \x00 o \xe0).
SPECIAL = {
    "H": b"\x1b[A",   # su
    "P": b"\x1b[B",   # giù
    "K": b"\x1b[D",   # sinistra
    "M": b"\x1b[C",   # destra
    "G": b"\x1b[H",   # Home
    "O": b"\x1b[F",   # End
    "I": b"\x1b[5~",  # PgUp
    "Q": b"\x1b[6~",  # PgDn
    "S": b"\x1b[3~",  # Canc
    "R": b"\x1b[2~",  # Ins
}

STD_OUTPUT_HANDLE = -11
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
kernel32 = ctypes.windll.kernel32


def enable_vt_output():
    h = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    mode = ctypes.c_uint()
    kernel32.GetConsoleMode(h, ctypes.byref(mode))
    kernel32.SetConsoleMode(h, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    return h, mode.value


def _config() -> dict:
    cfg = Path(__file__).resolve().parent / "config.json"
    try:
        return json.loads(cfg.read_text(encoding="utf-8"))
    except Exception:
        return {}


def default_port() -> int:
    try:
        return int(_config().get("attach_port", 8765))
    except Exception:
        return 8765


def input_thread(sock: socket.socket):
    try:
        while True:
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                code = msvcrt.getwch()
                if code in DETACH_FKEYS:  # F12 -> detach
                    sock.close()
                    return
                seq = SPECIAL.get(code)
                if seq:
                    sock.sendall(seq)
                continue
            if ch in DETACH_CHARS:  # Ctrl+] -> detach
                sock.close()
                return
            if ch == "\x08":  # Backspace -> DEL (convenzione dei TUI)
                sock.sendall(b"\x7f")
                continue
            sock.sendall(ch.encode("utf-8"))
    except OSError:
        return


def main():
    lang = _config().get("language")
    # optional args: <session id> <name> (for the window title)
    session = sys.argv[1] if len(sys.argv) > 1 else "active"
    if len(sys.argv) > 2 and sys.argv[2].strip():
        title = sys.argv[2].strip()
    elif session == "active":
        title = strings.tr(lang, "attach_active_title")
    else:
        title = strings.tr(lang, "attach_session_title", n=session)
    try:
        ctypes.windll.kernel32.SetConsoleTitleW(f"Telether — {title}")
    except Exception:
        pass
    port = default_port()
    try:
        sock = socket.create_connection((HOST, port))
    except OSError as exc:
        print(strings.tr(lang, "attach_conn_fail", host=HOST, port=port))
        print(strings.tr(lang, "attach_conn_hint", err=exc))
        return
    try:
        sock.sendall(f"ATTACH {session}\n".encode("utf-8"))
    except OSError:
        pass

    h_out, old_mode = enable_vt_output()
    sys.stdout.write("\x1b[2J\x1b[H" + strings.tr(lang, "attach_connected") + "\r\n")
    sys.stdout.flush()

    threading.Thread(target=input_thread, args=(sock,), daemon=True).start()

    try:
        while True:
            data = sock.recv(65536)
            if not data:
                break
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
    except OSError:
        pass
    finally:
        try:
            sock.close()
        except Exception:
            pass
        kernel32.SetConsoleMode(h_out, old_mode)
        sys.stdout.write("\r\n" + strings.tr(lang, "attach_detached") + "\r\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
