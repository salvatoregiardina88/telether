# Third-Party Licenses

Telether depends on the following open-source packages. They are installed
separately from PyPI via `pip` (see `requirements.txt` / `pyproject.toml`) and are
**not bundled or modified** by Telether. Each remains under its own license.

| Package | License | Project |
|---|---|---|
| python-telegram-bot | LGPL-3.0-only | https://github.com/python-telegram-bot/python-telegram-bot |
| pyte | LGPL-3.0 | https://github.com/selectel/pyte |
| pystray | LGPL-3.0 | https://github.com/moses-palmer/pystray |
| pywinpty | MIT | https://github.com/andfoy/pywinpty |
| Pillow | MIT-CMU (HPND) | https://github.com/python-pillow/Pillow |
| wcwidth | MIT | https://github.com/jquast/wcwidth |
| six | MIT | https://github.com/benjaminp/six |

## LGPL note

`python-telegram-bot`, `pyte` and `pystray` are licensed under the **GNU Lesser
General Public License v3 (LGPL-3.0)**. Telether uses them as **unmodified
libraries imported at runtime**, installed by the user from PyPI — it does not
statically link, bundle, or modify them. You are free to replace any of these
libraries with your own (for example by installing a different version with
`pip`). The full LGPL text is available at
<https://www.gnu.org/licenses/lgpl-3.0.html>.

Because these libraries are used dynamically and left unmodified, the LGPL does
not extend its terms to Telether's own code. Telether's source is therefore
licensed under **PolyForm Noncommercial 1.0.0** (see [LICENSE.md](LICENSE.md)),
which governs Telether's code only — not these dependencies, which keep the
licenses listed above.
