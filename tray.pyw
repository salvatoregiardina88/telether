#!/usr/bin/env pythonw
"""
Telether come app di sistema silenziosa.

Avvia il ponte in background (nessuna finestra, nessun suono) e mette
un'iconcina nella tray bar accanto all'orologio. Click destro sull'icona:
  - una voce per ogni sessione (● = attiva) -> aggancia quella sessione sul PC
  - "➕ Nuova sessione sul PC"               -> crea una sessione e ci si aggancia
  - "Esci"                                   -> chiude il ponte
Doppio click sull'icona = aggancia la sessione attiva.

Eseguire con pythonw.exe per non avere alcuna finestra di console.
"""

import asyncio
import ctypes
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# python.exe (con console) accanto a pythonw.exe, per aprire le finestre di attach
PYTHON_EXE = Path(sys.executable).with_name("python.exe")
ATTACH_PY = SCRIPT_DIR / "attach.py"

# --- Istanza singola: se il ponte è già attivo, esci subito. ----------------
if not os.environ.get("TELETHER_NO_SINGLETON"):
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Telether_singleton")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)

import pystray
from PIL import Image, ImageDraw
from telegram import Update

import bridge
import strings


def make_icon_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 8, 60, 56], radius=10, fill=(37, 99, 235, 255))
    # prompt ">"
    d.line([(16, 22), (26, 32), (16, 42)], fill=(255, 255, 255, 255), width=4, joint="curve")
    # cursore "_"
    d.rectangle([30, 40, 46, 44], fill=(255, 255, 255, 255))
    return img


def run_bridge():
    """Esegue il ponte nel proprio event loop, in un thread separato."""
    asyncio.set_event_loop(asyncio.new_event_loop())
    cfg = bridge.load_config()
    if not bridge.CONFIG_PATH.exists():
        bridge.save_config(cfg)
    token = (cfg.get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()
    if not token:
        # In silent mode we can't prompt for the token: just warn.
        ctypes.windll.user32.MessageBoxW(
            0,
            strings.tr(cfg.get("language"), "tray_no_token"),
            "Telether",
            0x10,  # MB_ICONERROR
        )
        os._exit(1)

    app = bridge.build_application(cfg, token)
    try:
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            stop_signals=None,   # obbligatorio fuori dal thread principale
            close_loop=False,
        )
    except Exception:
        pass


def launch_attach(session="active", name=""):
    """Apre una finestra di terminale agganciata alla sessione indicata."""
    try:
        if PYTHON_EXE.exists():
            args = [str(PYTHON_EXE), str(ATTACH_PY), str(session)]
            if name:
                args.append(name)
            subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:  # fallback: passa dall'.bat
            subprocess.Popen(
                ["cmd", "/c", "start", "", str(SCRIPT_DIR / "attach.bat"), str(session)]
            )
    except OSError:
        pass


def make_attach(session, name=""):
    return lambda icon, item: launch_attach(session, name)


def on_new_session(icon, item):
    """Crea una nuova sessione (nel loop del ponte) e ci si aggancia dal PC."""
    st = bridge.STATE
    if not st or not st.loop:
        return

    async def _mk():
        sess = bridge.create_session(st)
        st.last_version = -1
        st.want_new_message = True
        return sess

    try:
        fut = asyncio.run_coroutine_threadsafe(_mk(), st.loop)
        sess = fut.result(timeout=5)
    except Exception:
        return
    launch_attach(sess.id, sess.name)
    try:
        icon.update_menu()
    except Exception:
        pass


def on_quit(icon, item):
    icon.stop()
    try:
        if bridge.STATE:
            for s in bridge.STATE.sessions.values():
                s.term.stop()
    except Exception:
        pass
    os._exit(0)


def menu_items():
    """Menu dinamico: una voce per sessione + nuova sessione + esci."""
    st = bridge.STATE
    if st and st.sessions:
        for sid, sess in st.sessions.items():
            active = sid == st.active_id
            mark = "● " if active else "○ "
            dot = " •" if (sess.unread and not active) else ""
            yield pystray.MenuItem(
                f"{mark}{sess.name}{dot}", make_attach(sid, sess.name), default=active
            )
        yield pystray.Menu.SEPARATOR
    yield pystray.MenuItem(bridge.t("tray_new"), on_new_session)
    yield pystray.MenuItem(bridge.t("tray_quit"), on_quit)


def sessions_signature():
    st = bridge.STATE
    if not st:
        return None
    return (st.active_id, tuple((sid, s.name, s.unread) for sid, s in st.sessions.items()))


def menu_watcher(icon):
    """pystray non rivaluta il menu da solo: aggiornalo quando le sessioni cambiano."""
    last = "unset"
    while True:
        time.sleep(1.0)
        sig = sessions_signature()
        if sig != last:
            last = sig
            try:
                icon.update_menu()
            except Exception:
                pass


def main():
    threading.Thread(target=run_bridge, daemon=True).start()
    icon = pystray.Icon(
        "telether",
        make_icon_image(),
        "Telether — terminale ↔ Telegram",
        menu=pystray.Menu(menu_items),
    )
    threading.Thread(target=menu_watcher, args=(icon,), daemon=True).start()
    icon.run()


if __name__ == "__main__":
    main()
