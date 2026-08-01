"""Reusable Tk pieces. Plain ttk, no third-party themes.

The look is a dark, flat "setup assistant": near-black window, slightly
lighter cards with a hairline border, one blue accent, and status colours
that read at a glance. Everything is driven from the palette below — the
step files only ever reference style *names*.
"""

from __future__ import annotations

import os
import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Optional

from ..applog import CMD, DRY, ERROR, INFO, OK, OUT, STEP, WARN
from ..idioma import t

# --------------------------------------------------------------------------
# palette
# --------------------------------------------------------------------------

COL_BG = "#0f1218"          # window / content
COL_SIDEBAR = "#0a0d13"     # left rail
COL_CARD = "#171c26"        # cards
COL_CARD_HI = "#212836"     # hover / secondary buttons
COL_LINE = "#262e3d"        # hairlines
COL_TEXT = "#e7eaf3"
COL_MUTED = "#8b94a8"
COL_OK = "#48d17d"
COL_WARN = "#f2b23e"
COL_ERR = "#f26d5f"
COL_ACCENT = "#5b8cff"
COL_ACCENT_HI = "#7aa2ff"
COL_ACCENT_DARK = "#0c1430"
COL_FIELD = "#10141c"       # entry / text fields

LOG_BG = "#0a0d13"
LOG_COLOURS = {
    INFO: "#aeb4c4",
    STEP: "#7aa2ff",
    CMD: "#f0c674",
    DRY: "#c792ea",
    OUT: "#6f7788",
    OK: "#63e298",
    WARN: "#f2b23e",
    ERROR: "#ff7b72",
}

FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_H1 = ("Segoe UI", 17, "bold")
FONT_H2 = ("Segoe UI", 11, "bold")
FONT_MONO = ("Cascadia Mono", 9)
FONT_MONO_FALLBACK = ("Consolas", 9)


def _mono(root: tk.Misc):
    try:
        import tkinter.font as tkfont
        if "Cascadia Mono" in tkfont.families(root):
            return FONT_MONO
    except Exception:
        pass
    return FONT_MONO_FALLBACK


MONO = FONT_MONO_FALLBACK  # resolved for real inside apply_theme


def apply_theme(root: tk.Misc) -> None:
    global MONO
    MONO = _mono(root)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=COL_BG, foreground=COL_TEXT, font=FONT_UI,
                    bordercolor=COL_LINE, darkcolor=COL_BG, lightcolor=COL_BG,
                    troughcolor=COL_CARD, fieldbackground=COL_FIELD,
                    selectbackground=COL_ACCENT, selectforeground="#0b1020",
                    insertcolor=COL_TEXT)

    style.configure("TFrame", background=COL_BG)
    style.configure("Card.TFrame", background=COL_CARD, relief="solid",
                    borderwidth=1, bordercolor=COL_LINE)
    style.configure("TLabel", background=COL_BG, foreground=COL_TEXT)
    style.configure("Card.TLabel", background=COL_CARD)
    style.configure("H1.TLabel", font=FONT_H1)
    style.configure("H2.TLabel", font=FONT_H2)
    style.configure("Muted.TLabel", foreground=COL_MUTED)
    style.configure("Small.TLabel", foreground=COL_MUTED, font=FONT_SMALL)
    style.configure("CardMuted.TLabel", background=COL_CARD, foreground=COL_MUTED)
    style.configure("Ok.TLabel", foreground=COL_OK)
    style.configure("Warn.TLabel", foreground=COL_WARN)
    style.configure("Err.TLabel", foreground=COL_ERR)
    style.configure("CardOk.TLabel", background=COL_CARD, foreground=COL_OK)
    style.configure("CardWarn.TLabel", background=COL_CARD, foreground=COL_WARN)
    style.configure("CardErr.TLabel", background=COL_CARD, foreground=COL_ERR)

    for base in ("TCheckbutton", "TRadiobutton"):
        style.configure(base, background=COL_BG, foreground=COL_TEXT,
                        indicatorbackground=COL_FIELD, indicatorforeground=COL_ACCENT)
        style.map(base,
                  background=[("active", COL_BG)],
                  indicatorbackground=[("selected", COL_FIELD)],
                  foreground=[("disabled", COL_MUTED)])
        card = "Card." + base
        style.configure(card, background=COL_CARD, foreground=COL_TEXT,
                        indicatorbackground=COL_FIELD, indicatorforeground=COL_ACCENT)
        style.map(card, background=[("active", COL_CARD)],
                  foreground=[("disabled", COL_MUTED)])

    style.configure("TButton", padding=(14, 8), background=COL_CARD_HI,
                    foreground=COL_TEXT, bordercolor=COL_LINE, relief="flat",
                    focuscolor=COL_ACCENT)
    style.map("TButton",
              background=[("disabled", COL_CARD), ("pressed", "#2a3345"),
                          ("active", "#2a3345")],
              foreground=[("disabled", COL_MUTED)])
    style.configure("Accent.TButton", padding=(18, 9), font=FONT_UI_BOLD,
                    background=COL_ACCENT, foreground="#0b1020",
                    bordercolor=COL_ACCENT)
    style.map("Accent.TButton",
              background=[("disabled", "#31405f"), ("pressed", COL_ACCENT_HI),
                          ("active", COL_ACCENT_HI)],
              foreground=[("disabled", "#7d879e")])
    style.configure("Ghost.TButton", padding=(10, 5), background=COL_BG,
                    foreground=COL_MUTED, bordercolor=COL_LINE)
    style.map("Ghost.TButton", background=[("active", COL_CARD_HI)],
              foreground=[("active", COL_TEXT)])

    style.configure("TEntry", fieldbackground=COL_FIELD, foreground=COL_TEXT,
                    bordercolor=COL_LINE, insertcolor=COL_TEXT, padding=6)
    style.map("TEntry", bordercolor=[("focus", COL_ACCENT)],
              fieldbackground=[("disabled", COL_CARD)])
    style.configure("TCombobox", fieldbackground=COL_FIELD, foreground=COL_TEXT,
                    background=COL_CARD_HI, bordercolor=COL_LINE,
                    arrowcolor=COL_MUTED, padding=5)
    style.map("TCombobox",
              fieldbackground=[("readonly", COL_FIELD), ("disabled", COL_CARD)],
              foreground=[("disabled", COL_MUTED)],
              bordercolor=[("focus", COL_ACCENT)])
    root.option_add("*TCombobox*Listbox.background", COL_CARD)
    root.option_add("*TCombobox*Listbox.foreground", COL_TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", COL_ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#0b1020")

    style.configure("Horizontal.TProgressbar", troughcolor=COL_CARD,
                    background=COL_ACCENT, borderwidth=0, thickness=8,
                    lightcolor=COL_ACCENT, darkcolor=COL_ACCENT)

    style.configure("Treeview", rowheight=26, background=COL_CARD,
                    fieldbackground=COL_CARD, foreground=COL_TEXT,
                    bordercolor=COL_LINE)
    style.map("Treeview",
              background=[("selected", COL_ACCENT)],
              foreground=[("selected", "#0b1020")])
    style.configure("Treeview.Heading", font=FONT_UI_BOLD, background=COL_CARD_HI,
                    foreground=COL_TEXT, bordercolor=COL_LINE, relief="flat")
    style.map("Treeview.Heading", background=[("active", "#2a3345")])

    for orient in ("Vertical", "Horizontal"):
        style.configure(f"{orient}.TScrollbar", background=COL_CARD_HI,
                        troughcolor=COL_BG, bordercolor=COL_BG,
                        arrowcolor=COL_MUTED, relief="flat")
        style.map(f"{orient}.TScrollbar", background=[("active", "#2a3345")])

    style.configure("TSeparator", background=COL_LINE)
    style.configure("TPanedwindow", background=COL_BG)
    style.configure("Sash", sashthickness=6, background=COL_BG)


class ScrollFrame(ttk.Frame):
    """Vertically scrollable container that behaves when the window resizes."""

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(self, bg=COL_BG, highlightthickness=0, bd=0)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar.pack(side="right", fill="y")
        self.body.bind("<Configure>", self._on_body)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.bind("<Enter>", lambda _e: self._bind_wheel(True))
        self.canvas.bind("<Leave>", lambda _e: self._bind_wheel(False))

    def _on_body(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, event) -> None:
        self.canvas.itemconfigure(self._win, width=event.width)

    def _bind_wheel(self, on: bool) -> None:
        if on:
            self.canvas.bind_all("<MouseWheel>", self._wheel)
            self.canvas.bind_all("<Button-4>", self._wheel)
            self.canvas.bind_all("<Button-5>", self._wheel)
        else:
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")

    def _wheel(self, event) -> None:
        if not self.canvas.winfo_exists():
            return
        first, last = self.canvas.yview()
        if first <= 0.0 and last >= 1.0:
            return
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        else:
            delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, "units")


class Card(ttk.Frame):
    """A bordered block with an optional title."""

    def __init__(self, master, title: str = "", **kw):
        super().__init__(master, style="Card.TFrame", padding=16, **kw)
        if title:
            ttk.Label(self, text=title, style="H2.TLabel",
                      background=COL_CARD).pack(anchor="w", pady=(0, 10))


def body_label(master, text: str, *, style: str = "Card.TLabel",
               width: int = 96, **kw) -> ttk.Label:
    lbl = ttk.Label(master, text=text, style=style, justify="left",
                    wraplength=760, **kw)
    lbl.pack(anchor="w", pady=2, fill="x")
    return lbl


def link(master, text: str, url: str, **kw) -> tk.Label:
    lbl = tk.Label(master, text=text, fg=COL_ACCENT_HI, cursor="hand2",
                   bg=kw.pop("bg", COL_CARD), font=FONT_UI, anchor="w",
                   justify="left")
    lbl.bind("<Button-1>", lambda _e: webbrowser.open(url))
    lbl.bind("<Enter>", lambda _e: lbl.configure(fg="#a5c0ff"))
    lbl.bind("<Leave>", lambda _e: lbl.configure(fg=COL_ACCENT_HI))
    lbl.pack(anchor="w", pady=2)
    return lbl


class LogPane(ttk.Frame):
    """Live log with colouring by level and a 'follow' toggle."""

    MAX_LINES = 4000

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        head = ttk.Frame(self)
        head.pack(fill="x")
        ttk.Label(head, text=t("pane.title"), style="Small.TLabel",
                  font=("Segoe UI", 8, "bold")).pack(side="left")
        self.follow = tk.BooleanVar(value=True)
        ttk.Checkbutton(head, text=t("pane.follow"), variable=self.follow).pack(side="right")

        wrap = tk.Frame(self, bg=COL_LINE, padx=1, pady=1)
        wrap.pack(fill="both", expand=True, pady=(6, 0))
        inner = tk.Frame(wrap, bg=LOG_BG)
        inner.pack(fill="both", expand=True)
        self.text = tk.Text(inner, bg=LOG_BG, fg="#aeb4c4", insertbackground="#aeb4c4",
                            font=MONO, wrap="none", height=10,
                            relief="flat", padx=10, pady=8,
                            selectbackground=COL_ACCENT, selectforeground="#0b1020")
        ybar = ttk.Scrollbar(inner, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=ybar.set)
        self.text.pack(side="left", fill="both", expand=True)
        ybar.pack(side="right", fill="y")

        for level, colour in LOG_COLOURS.items():
            self.text.tag_configure(level, foreground=colour)
        self.text.tag_configure(STEP, foreground=LOG_COLOURS[STEP],
                                font=(MONO[0], MONO[1], "bold"))
        self.text.configure(state="disabled")
        self._lines = 0

    def append(self, level: str, message: str) -> None:
        prefix = {STEP: "", CMD: "  $ ", DRY: " ~$ ", OUT: "  │ ",
                  OK: "  ✓ ", WARN: "  ! ", ERROR: "  ✕ "}.get(level, "    ")
        self.text.configure(state="normal")
        for line in (message or "").splitlines() or [""]:
            self.text.insert("end", prefix + line + "\n", level)
            self._lines += 1
        if self._lines > self.MAX_LINES:
            drop = self._lines - self.MAX_LINES
            self.text.delete("1.0", f"{drop + 1}.0")
            self._lines -= drop
        self.text.configure(state="disabled")
        if self.follow.get():
            self.text.see("end")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self._lines = 0


class ProgressRow(ttk.Frame):
    """A label plus a bar that can be determinate or indeterminate."""

    def __init__(self, master, **kw):
        super().__init__(master, style="Card.TFrame", **kw)
        self.label = ttk.Label(self, text="", style="CardMuted.TLabel")
        self.label.pack(anchor="w")
        self.bar = ttk.Progressbar(self, mode="determinate", maximum=1000)
        self.bar.pack(fill="x", pady=(5, 0))
        self._running = False

    def set(self, done: int, total: int, prefix: str = "") -> None:
        if total and total > 0:
            self.bar.configure(mode="determinate")
            self.bar["value"] = max(0, min(1000, int(done * 1000 / total)))
            pct = done * 100.0 / total
            self.label.configure(
                text=t("progress.of", feito=f"{done / 1e6:.1f}",
                         total=f"{total / 1e6:.1f}", pct=f"{pct:.0f}",
                         prefixo=prefix)
            )
        else:
            self.label.configure(text=f"{prefix}{done / 1e6:.1f} MB")

    def busy(self, text: str) -> None:
        self.label.configure(text=text)
        if not self._running:
            self.bar.configure(mode="indeterminate")
            self.bar.start(50)
            self._running = True

    def stop(self, text: str = "") -> None:
        if self._running:
            self.bar.stop()
            self._running = False
        self.bar.configure(mode="determinate")
        self.bar["value"] = 1000 if text else 0
        self.label.configure(text=text)

    def reset(self) -> None:
        self.stop("")
        self.bar["value"] = 0
        self.label.configure(text="")


class StatusLine(ttk.Frame):
    """Symbol + text, used for check lists."""

    SYMBOLS = {"ok": ("✓", "CardOk.TLabel"),
               "warn": ("!", "CardWarn.TLabel"),
               "fail": ("✕", "CardErr.TLabel"),
               "unknown": ("·", "CardMuted.TLabel"),
               "busy": ("…", "CardMuted.TLabel")}

    def __init__(self, master, title: str, **kw):
        super().__init__(master, style="Card.TFrame", **kw)
        self.symbol = ttk.Label(self, text="·", style="CardMuted.TLabel",
                                width=3, font=FONT_UI_BOLD)
        self.symbol.grid(row=0, column=0, sticky="nw")
        self.title = ttk.Label(self, text=title, style="Card.TLabel",
                               font=FONT_UI_BOLD)
        self.title.grid(row=0, column=1, sticky="w")
        self.detail = ttk.Label(self, text="", style="CardMuted.TLabel",
                                wraplength=680, justify="left")
        self.detail.grid(row=1, column=1, sticky="w")
        self.hint = ttk.Label(self, text="", style="CardWarn.TLabel",
                              wraplength=680, justify="left")
        self.columnconfigure(1, weight=1)
        self.actions = ttk.Frame(self, style="Card.TFrame")
        self._hint_shown = False

    def update_state(self, status: str, detail: str = "", hint: str = "") -> None:
        symbol, style = self.SYMBOLS.get(status, self.SYMBOLS["unknown"])
        self.symbol.configure(text=symbol, style=style)
        self.detail.configure(text=detail)
        if hint:
            self.hint.configure(text=hint)
            if not self._hint_shown:
                self.hint.grid(row=2, column=1, sticky="w", pady=(4, 0))
                self._hint_shown = True
        elif self._hint_shown:
            self.hint.grid_forget()
            self._hint_shown = False


class ReadOnlyText(ttk.Frame):
    def __init__(self, master, height: int = 10, mono: bool = True, **kw):
        super().__init__(master, **kw)
        outer = tk.Frame(self, bg=COL_LINE, padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        self.text = tk.Text(outer, height=height, wrap="word", relief="flat",
                            padx=10, pady=8,
                            font=MONO if mono else FONT_UI,
                            background=COL_FIELD, foreground=COL_TEXT,
                            insertbackground=COL_TEXT,
                            selectbackground=COL_ACCENT,
                            selectforeground="#0b1020")
        bar = ttk.Scrollbar(outer, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=bar.set, state="disabled")
        self.text.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")

    def set(self, content: str) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.configure(state="disabled")


def dark_text(master, height: int = 10, mono: bool = True, wrap: str = "none") -> tk.Text:
    """An editable text field in the theme, wrapped in a hairline border."""
    outer = tk.Frame(master, bg=COL_LINE, padx=1, pady=1)
    outer.pack(fill="both", expand=True, pady=(8, 0))
    text = tk.Text(outer, height=height, wrap=wrap, relief="flat",
                   padx=10, pady=8, font=MONO if mono else FONT_UI,
                   background=COL_FIELD, foreground=COL_TEXT,
                   insertbackground=COL_TEXT,
                   selectbackground=COL_ACCENT, selectforeground="#0b1020")
    text.pack(fill="both", expand=True)
    return text


class Tooltip:
    """Hover help. Plain Toplevel — ttk has no tooltip, and a label that is
    always visible would crowd screens that are already dense."""

    def __init__(self, widget, text: str, delay: int = 500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after: Optional[str] = None
        self._win: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._after = self.widget.after(self.delay, self._show)

    def _cancel(self) -> None:
        if self._after:
            try:
                self.widget.after_cancel(self._after)
            except Exception:
                pass
            self._after = None

    def _show(self) -> None:
        if self._win or not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._win = tk.Toplevel(self.widget)
        self._win.wm_overrideredirect(True)
        self._win.wm_geometry(f"+{x}+{y}")
        frame = tk.Frame(self._win, bg=COL_LINE, padx=1, pady=1)
        frame.pack()
        tk.Label(frame, text=self.text, bg=COL_CARD_HI, fg=COL_TEXT,
                 font=FONT_SMALL, justify="left", wraplength=340,
                 padx=10, pady=7).pack()

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._win:
            self._win.destroy()
            self._win = None


def tip(widget, text: str) -> None:
    Tooltip(widget, text)


def reveal(path: str) -> None:
    """Open a file or folder in the platform's file manager / default app."""
    import subprocess
    import sys as _sys

    if not path:
        return
    try:
        if _sys.platform.startswith("win"):
            if os.path.isdir(path):
                os.startfile(path)  # noqa: S606
            else:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif _sys.platform == "darwin":
            subprocess.Popen(["open", "-R" if os.path.isfile(path) else path, path]
                             if os.path.isfile(path) else ["open", path])
        else:
            target = path if os.path.isdir(path) else os.path.dirname(path)
            subprocess.Popen(["xdg-open", target])
    except Exception:
        pass


def show_error(master, title: str, message: str, detail: str = "",
               files: Optional[list[tuple[str, str]]] = None) -> None:
    """A resizable error window — tracebacks and tool output need room.

    ``files`` adds one button per (label, path): printing a path and leaving the
    user to go find it is not much help when the point is to hand them a script
    they can re-run.
    """
    win = tk.Toplevel(master)
    win.title(title)
    win.configure(bg=COL_BG)
    win.geometry("800x480")
    win.transient(master.winfo_toplevel())

    frame = ttk.Frame(win, padding=18)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=title, style="H2.TLabel", foreground=COL_ERR).pack(anchor="w")
    ttk.Label(frame, text=message, wraplength=740, justify="left").pack(
        anchor="w", pady=(8, 12), fill="x")
    if detail:
        box = ReadOnlyText(frame, height=12)
        box.pack(fill="both", expand=True)
        box.set(detail)

    existing = [(label, path) for label, path in (files or [])
                if path and os.path.exists(path)]
    if existing:
        bar = ttk.Frame(frame)
        bar.pack(fill="x", pady=(12, 0))
        ttk.Label(bar, text=t("dlg.files"), style="Muted.TLabel").pack(side="left",
                                                                    padx=(0, 8))
        for label, path in existing:
            btn = ttk.Button(bar, text=label, command=lambda p=path: reveal(p))
            btn.pack(side="left", padx=(0, 6))
            Tooltip(btn, path)

    row = ttk.Frame(frame)
    row.pack(fill="x", pady=(14, 0))

    def copy() -> None:
        extra = "\n".join(f"{label}: {path}" for label, path in (files or []))
        win.clipboard_clear()
        win.clipboard_append(f"{title}\n\n{message}\n\n{detail}"
                             + (f"\n\n{extra}" if extra else ""))

    ttk.Button(row, text=t("dlg.copy"), command=copy).pack(side="left")
    ttk.Button(row, text=t("dlg.close"), style="Accent.TButton",
               command=win.destroy).pack(side="right")
    win.grab_set()


def confirm(master, title: str, message: str, ok_text: str = "",
            cancel_text: str = "", danger: bool = False) -> bool:
    """Modal yes/no with wording we control (messagebox is not translatable)."""
    win = tk.Toplevel(master)
    win.title(title)
    win.configure(bg=COL_BG)
    win.transient(master.winfo_toplevel())
    win.resizable(False, False)
    result = {"value": False}
    ok_text = ok_text or t("dlg.ok")
    cancel_text = cancel_text or t("dlg.cancel")

    frame = ttk.Frame(win, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=title, style="H2.TLabel",
              foreground=COL_ERR if danger else COL_TEXT).pack(anchor="w")
    ttk.Label(frame, text=message, wraplength=520, justify="left").pack(
        anchor="w", pady=(10, 16))
    row = ttk.Frame(frame)
    row.pack(fill="x")

    def yes() -> None:
        result["value"] = True
        win.destroy()

    ttk.Button(row, text=cancel_text, command=win.destroy).pack(side="right")
    ttk.Button(row, text=ok_text, command=yes,
               style="Accent.TButton").pack(side="right", padx=(0, 8))
    win.grab_set()
    win.wait_window()
    return result["value"]


def choose(master, title: str, message: str,
           options: list[tuple[str, str, str]]) -> Optional[str]:
    """Modal with several labelled choices. options = [(key, label, help)]."""
    win = tk.Toplevel(master)
    win.title(title)
    win.configure(bg=COL_BG)
    win.transient(master.winfo_toplevel())
    win.resizable(False, False)
    result: dict[str, Optional[str]] = {"value": None}

    frame = ttk.Frame(win, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=title, style="H2.TLabel").pack(anchor="w")
    ttk.Label(frame, text=message, wraplength=560, justify="left").pack(
        anchor="w", pady=(10, 14))

    choice = tk.StringVar(value=options[0][0])
    for key, label, helptext in options:
        ttk.Radiobutton(frame, text=label, value=key, variable=choice).pack(anchor="w")
        if helptext:
            ttk.Label(frame, text=helptext, style="Muted.TLabel", wraplength=520,
                      justify="left").pack(anchor="w", padx=(24, 0), pady=(0, 6))

    row = ttk.Frame(frame)
    row.pack(fill="x", pady=(12, 0))

    def ok() -> None:
        result["value"] = choice.get()
        win.destroy()

    ttk.Button(row, text=t("dlg.cancel"), command=win.destroy).pack(side="right")
    ttk.Button(row, text=t("dlg.confirm"), command=ok,
               style="Accent.TButton").pack(side="right", padx=(0, 8))
    win.grab_set()
    win.wait_window()
    return result["value"]
