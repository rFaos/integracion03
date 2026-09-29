"""Tema visual de la aplicacion (colores, tipografia y estilos ttk).

Se centraliza aqui para que ninguna vista escriba colores a mano: cambiar la
paleta es cambiar este archivo.
"""

import tkinter as tk
from tkinter import ttk

# ------------------------------------------------------------------------------
# Paleta
# ------------------------------------------------------------------------------
COLORS = {
    "bg": "#f4f6f8",
    "surface": "#ffffff",
    "surface_alt": "#eef1f5",
    "border": "#d6dbe1",
    "text": "#1f2328",
    "muted": "#5f6b7a",
    "primary": "#1a73e8",
    "primary_dark": "#1557b0",
    "primary_soft": "#e8f0fe",
    "ok": "#1e8e3e",
    "warn": "#e8a600",
    "danger": "#d93025",
    "danger_dark": "#a5271d",
    "dark": "#243044",
}

# ------------------------------------------------------------------------------
# Tipografia (Segoe UI existe en Windows 10/11; Tk elige una parecida en otros)
# ------------------------------------------------------------------------------
FONT_BASE = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_H1 = ("Segoe UI Semibold", 20, "bold")
FONT_H2 = ("Segoe UI Semibold", 14, "bold")
FONT_H3 = ("Segoe UI Semibold", 11, "bold")
FONT_MONO = ("Consolas", 9)


def apply_theme(root):
    """Aplica el tema a toda la ventana. Debe llamarse una sola vez."""
    style = ttk.Style(root)
    # 'clam' permite controlar el color de fondo de los widgets en Windows.
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root.configure(bg=COLORS["bg"])

    style.configure(".", font=FONT_BASE, background=COLORS["bg"], foreground=COLORS["text"])

    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Surface.TFrame", background=COLORS["surface"])
    style.configure("Alt.TFrame", background=COLORS["surface_alt"])

    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("Surface.TLabel", background=COLORS["surface"], foreground=COLORS["text"])
    style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=FONT_SMALL)
    style.configure("SurfaceMuted.TLabel", background=COLORS["surface"],
                    foreground=COLORS["muted"], font=FONT_SMALL)
    style.configure("H1.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONT_H1)
    style.configure("H2.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONT_H2)
    style.configure("H3.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONT_H3)
    style.configure("SurfaceH3.TLabel", background=COLORS["surface"],
                    foreground=COLORS["text"], font=FONT_H3)

    # --- botones -------------------------------------------------------------
    style.configure("TButton", font=FONT_BASE, padding=(12, 7), borderwidth=0,
                    background=COLORS["surface_alt"], foreground=COLORS["text"])
    # El estado "disabled" se define de forma explicita: sin este mapeo, el tema
    # nativo de Windows pinta el texto casi invisible y los botones de
    # paginacion parecen vacios cuando estan deshabilitados.
    style.map("TButton",
              background=[("active", COLORS["border"])],
              foreground=[("disabled", COLORS["muted"])])

    style.configure("Primary.TButton", background=COLORS["primary"], foreground="#ffffff",
                    font=FONT_BOLD)
    style.map("Primary.TButton",
              background=[("active", COLORS["primary_dark"]), ("disabled", "#9fb8e0")],
              foreground=[("disabled", "#eef3fb")])

    style.configure("Danger.TButton", background=COLORS["danger"], foreground="#ffffff",
                    font=FONT_BOLD)
    style.map("Danger.TButton",
              background=[("active", COLORS["danger_dark"]), ("disabled", "#e3a49f")],
              foreground=[("disabled", "#fdf1f0")])

    style.configure("Ghost.TButton", background=COLORS["surface"], foreground=COLORS["primary"],
                    font=FONT_BOLD, borderwidth=1, relief="solid")
    style.map("Ghost.TButton",
              background=[("active", COLORS["primary_soft"])],
              foreground=[("disabled", COLORS["muted"])])

    style.configure("Link.TButton", background=COLORS["bg"], foreground=COLORS["primary"],
                    font=FONT_BOLD, padding=(6, 4))
    style.map("Link.TButton", background=[("active", COLORS["bg"])])

    style.configure("SurfaceLink.TButton", background=COLORS["surface"],
                    foreground=COLORS["primary"], font=FONT_BOLD, padding=(6, 4))
    style.map("SurfaceLink.TButton", background=[("active", COLORS["surface"])])

    # --- entradas ------------------------------------------------------------
    style.configure("TEntry", fieldbackground="#ffffff", bordercolor=COLORS["border"],
                    lightcolor=COLORS["border"], darkcolor=COLORS["border"], padding=6)
    style.map("TEntry", bordercolor=[("focus", COLORS["primary"])])

    style.configure("TCombobox", fieldbackground="#ffffff", background="#ffffff",
                    bordercolor=COLORS["border"], arrowcolor=COLORS["muted"], padding=4)
    style.map("TCombobox", fieldbackground=[("readonly", "#ffffff")])

    style.configure("TCheckbutton", background=COLORS["bg"], foreground=COLORS["text"], font=FONT_BASE)
    style.configure("Surface.TCheckbutton", background=COLORS["surface"],
                    foreground=COLORS["text"], font=FONT_BASE)
    style.map("TCheckbutton", background=[("active", COLORS["bg"])])
    style.map("Surface.TCheckbutton", background=[("active", COLORS["surface"])])

    style.configure("TRadiobutton", background=COLORS["surface"], foreground=COLORS["text"])

    # --- separadores y barras ------------------------------------------------
    style.configure("TSeparator", background=COLORS["border"])
    style.configure("TProgressbar", background=COLORS["primary"], troughcolor=COLORS["surface_alt"],
                    borderwidth=0)

    # --- pestañas (panel principal) -----------------------------------------
    style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", padding=(16, 9), font=FONT_BOLD,
                    background=COLORS["surface_alt"], foreground=COLORS["muted"])
    style.map("TNotebook.Tab",
              background=[("selected", COLORS["surface"])],
              foreground=[("selected", COLORS["primary"])])

    # --- tabla (conceptos del libro) ----------------------------------------
    style.configure("Treeview", background=COLORS["surface"], fieldbackground=COLORS["surface"],
                    foreground=COLORS["text"], rowheight=24, borderwidth=0, font=FONT_SMALL)
    style.configure("Treeview.Heading", font=FONT_BOLD, background=COLORS["surface_alt"],
                    foreground=COLORS["text"], relief="flat")
    style.map("Treeview", background=[("selected", COLORS["primary_soft"])],
              foreground=[("selected", COLORS["text"])])

    style.configure("Vertical.TScrollbar", background=COLORS["surface_alt"],
                    troughcolor=COLORS["bg"], bordercolor=COLORS["bg"], arrowcolor=COLORS["muted"])
    style.configure("Horizontal.TScrollbar", background=COLORS["surface_alt"],
                    troughcolor=COLORS["bg"], bordercolor=COLORS["bg"], arrowcolor=COLORS["muted"])

    return style
