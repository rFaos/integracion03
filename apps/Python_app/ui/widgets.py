"""Widgets reutilizables: semaforo, tarjetas de libro, imagenes y avisos."""

import queue
import threading
import tkinter as tk
import urllib.request
from tkinter import ttk

from .theme import COLORS, FONT_BASE, FONT_BOLD, FONT_H2, FONT_H3, FONT_MONO, FONT_SMALL

# Pillow es OPCIONAL: si no esta instalado, la aplicacion funciona igual y
# muestra un recuadro "Sin imagen" en lugar de la portada.
try:
    from PIL import Image, ImageTk
    PILLOW_AVAILABLE = True
except ImportError:                                    # pragma: no cover
    PILLOW_AVAILABLE = False

# La portada que devuelve el catalogo cuando el libro NO tiene imagenes
# registradas es una URL generica de Unsplash (COALESCE del microservicio).
# Se detecta para no mostrar como portada algo que no pertenece al libro.
FALLBACK_COVER_MARKER = "photo-1544716278-ca5e3f4abd8c"


def is_placeholder_cover(url):
    """True si la portada es la imagen generica del servicio, no del libro."""
    return bool(url) and FALLBACK_COVER_MARKER in url


# ==============================================================================
# Imagenes
# ==============================================================================
class ImageLoader:
    """Descarga portadas en segundo plano y las convierte a PhotoImage.

    Tkinter exige que los objetos PhotoImage se creen en el hilo principal, por
    eso el hilo solo descarga bytes y la conversion ocurre en `_poll`.
    """

    def __init__(self, master, timeout=6.0, cache_limit=120):
        self.master = master
        self.timeout = timeout
        self.cache_limit = cache_limit
        self._cache = {}            # clave -> PhotoImage | None
        self._waiters = {}          # clave -> [callbacks]
        self._bytes = queue.Queue()
        self._active = set()
        self._lock = threading.Lock()
        self._polling = True
        self.master.after(100, self._poll)

    # ------------------------------------------------------------------ publico
    def get(self, url, size, callback):
        """Pide la imagen `url` al tamano `size`; llama a callback(PhotoImage|None)."""
        if not url:
            callback(None)
            return
        key = (url, size)
        with self._lock:
            if key in self._cache:
                photo = self._cache[key]
                self.master.after(0, lambda: callback(photo))
                return
            if key in self._waiters:
                self._waiters[key].append(callback)
                return
            self._waiters[key] = [callback]
            if key in self._active:
                return
            self._active.add(key)

        threading.Thread(target=self._download, args=(url, size), daemon=True).start()

    def shutdown(self):
        self._polling = False

    # ------------------------------------------------------------------- hilos
    def _download(self, url, size):
        key = (url, size)
        payload = None
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "PythonApp-Biblioteca/1.0"})
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except Exception:
            payload = None
        self._bytes.put((key, payload))

    def _poll(self):
        """Crea los PhotoImage en el hilo de Tk y avisa a quien los esperaba."""
        while True:
            try:
                key, payload = self._bytes.get_nowait()
            except queue.Empty:
                break

            photo = self._to_photo(payload, key[1])
            with self._lock:
                if len(self._cache) >= self.cache_limit:
                    self._cache.clear()          # cache sencilla por tamano
                self._cache[key] = photo
                callbacks = self._waiters.pop(key, [])
                self._active.discard(key)
            for callback in callbacks:
                try:
                    callback(photo)
                except tk.TclError:
                    pass                         # la tarjeta ya no existe

        if self._polling:
            self.master.after(120, self._poll)

    @staticmethod
    def _to_photo(payload, size):
        if not payload or not PILLOW_AVAILABLE:
            return None
        try:
            from io import BytesIO
            image = Image.open(BytesIO(payload)).convert("RGB")
            image.thumbnail(size, Image.LANCZOS)
            return ImageTk.PhotoImage(image)
        except Exception:
            return None


class CoverBox(tk.Frame):
    """Recuadro de portada: muestra la imagen o un aviso de que no existe.

    Nunca lanza error si el libro no tiene imagen, si la URL esta rota o si la
    descarga falla: en todos esos casos queda visible el texto del marcador.
    """

    def __init__(self, master, size=(150, 200), text="Sin imagen", **kwargs):
        super().__init__(master, width=size[0], height=size[1],
                         bg=COLORS["surface_alt"], highlightthickness=1,
                         highlightbackground=COLORS["border"], **kwargs)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.size = size
        self._label = tk.Label(self, text=text, bg=COLORS["surface_alt"], fg=COLORS["muted"],
                               font=FONT_SMALL, wraplength=size[0] - 14, justify="center")
        self._label.place(relx=0.5, rely=0.5, anchor="center")
        self._photo = None

    def show_photo(self, photo):
        if photo is None:
            return
        self._photo = photo                     # referencia obligatoria
        self._label.configure(image=photo, text="", bg=COLORS["surface_alt"])
        self._label.place(relx=0.5, rely=0.5, anchor="center")

    def set_text(self, text):
        self._photo = None
        self._label.configure(image="", text=text)


# ==============================================================================
# Contenedores
# ==============================================================================
class Card(tk.Frame):
    """Panel blanco con borde, usado como bloque de contenido."""

    def __init__(self, master, padding=16, **kwargs):
        super().__init__(master, bg=COLORS["surface"], highlightthickness=1,
                         highlightbackground=COLORS["border"], **kwargs)
        self.body = tk.Frame(self, bg=COLORS["surface"])
        self.body.pack(fill="both", expand=True, padx=padding, pady=padding)


class ScrollableFrame(tk.Frame):
    """Frame con barra de desplazamiento vertical (para rejillas de tarjetas)."""

    def __init__(self, master, bg=None, **kwargs):
        super().__init__(master, bg=bg or COLORS["bg"], **kwargs)
        self.canvas = tk.Canvas(self, bg=bg or COLORS["bg"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg or COLORS["bg"])

        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", lambda _e: self._bind_wheel())
        self.canvas.bind("<Leave>", lambda _e: self._unbind_wheel())

    def _on_inner_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def reset_scroll(self):
        self.canvas.yview_moveto(0)


class StatusLight(tk.Frame):
    """Semaforo de estado de un microservicio.

    Pinta el circulo con el color del estado y muestra la hora de la ultima
    comprobacion, que es un requisito explicito de la actividad.
    """

    def __init__(self, master, service_key, label, on_click=None, bg=None):
        super().__init__(master, bg=bg or COLORS["surface"])
        self.service_key = service_key

        self.canvas = tk.Canvas(self, width=18, height=18, highlightthickness=0,
                                bg=bg or COLORS["surface"], cursor="hand2" if on_click else "")
        self.canvas.pack(side="left")
        self._circle = self.canvas.create_oval(3, 3, 15, 15, fill=COLORS["muted"], outline="")

        self.text = tk.Label(self, text=f"{label}: comprobando...", bg=bg or COLORS["surface"],
                             fg=COLORS["text"], font=FONT_SMALL, anchor="w", cursor="hand2" if on_click else "")
        self.text.pack(side="left", padx=(6, 0))

        if on_click:
            for widget in (self.canvas, self.text):
                widget.bind("<Button-1>", lambda _e: on_click(service_key))

    def set_result(self, result):
        """Aplica un HealthResult al semaforo."""
        if result is None:
            return
        self.canvas.itemconfigure(self._circle, fill=result.color)
        detail = f" · HTTP {result.http_status}" if result.http_status else ""
        self.text.configure(
            text=f"{result.label}: {result.state_label} ({result.checked_at_text()}){detail}")
        self.tooltip_text = result.summary()
        self.text.bind("<Enter>", self._show_tip)
        self.text.bind("<Leave>", self._hide_tip)

    # Tooltip sencillo con el detalle de la comprobacion.
    def _show_tip(self, _event):
        text = getattr(self, "tooltip_text", "")
        if not text:
            return
        self._tip = tk.Toplevel(self)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + 22}")
        tk.Label(self._tip, text=text, bg="#fffbe6", fg=COLORS["text"], font=FONT_SMALL,
                 relief="solid", borderwidth=1, justify="left", padx=8, pady=5).pack()

    def _hide_tip(self, _event):
        tip = getattr(self, "_tip", None)
        if tip is not None:
            tip.destroy()
            self._tip = None


class Banner(tk.Frame):
    """Aviso en linea (exito / error / informacion) con boton para cerrarlo."""

    STYLES = {
        "success": (COLORS["ok"], "#e6f4ea"),
        "error": (COLORS["danger"], "#fce8e6"),
        "warning": (COLORS["warn"], "#fef7e0"),
        "info": (COLORS["primary"], COLORS["primary_soft"]),
    }

    def __init__(self, master, **kwargs):
        super().__init__(master, bg=COLORS["surface"], **kwargs)
        self._visible = False

    def show(self, message, kind="info", technical=None):
        self.clear()
        border, background = self.STYLES.get(kind, self.STYLES["info"])
        self.configure(bg=background, highlightthickness=1, highlightbackground=border)
        wrap = tk.Frame(self, bg=background)
        wrap.pack(fill="x", padx=12, pady=8)

        tk.Label(wrap, text=message, bg=background, fg=COLORS["text"], font=FONT_BASE,
                 justify="left", anchor="w", wraplength=880).pack(side="left", fill="x", expand=True)
        if technical:
            tk.Label(wrap, text=technical, bg=background, fg=COLORS["muted"], font=FONT_SMALL,
                     justify="left", anchor="w", wraplength=880).pack(side="left", padx=(12, 0))
        tk.Button(wrap, text="x", command=self.clear, bg=background, fg=COLORS["muted"],
                  relief="flat", borderwidth=0, font=FONT_BOLD, cursor="hand2").pack(side="right")
        self._visible = True

    def clear(self):
        for child in self.winfo_children():
            child.destroy()
        self.configure(bg=COLORS["surface"], highlightthickness=0)
        self._visible = False


class SectionTitle(tk.Frame):
    """Titulo de seccion con subtitulo opcional."""

    def __init__(self, master, title, subtitle=None, bg=None):
        super().__init__(master, bg=bg or COLORS["bg"])
        tk.Label(self, text=title, bg=bg or COLORS["bg"], fg=COLORS["text"],
                 font=FONT_H2, anchor="w").pack(anchor="w")
        if subtitle:
            tk.Label(self, text=subtitle, bg=bg or COLORS["bg"], fg=COLORS["muted"],
                     font=FONT_SMALL, anchor="w", justify="left").pack(anchor="w")


# ==============================================================================
# Tarjeta de libro
# ==============================================================================
class BookCard(tk.Frame):
    """Tarjeta del catalogo.

    Muestra los datos que pide la actividad (ISBN, titulo, autor, genero, anio,
    precio, existencia, formato, categoria e imagen) y avisa cuando el libro no
    tiene imagen propia.
    """

    def __init__(self, master, book, on_open, image_loader, image_size=(150, 200),
                 on_edit=None, on_delete=None, show_actions=False, **kwargs):
        super().__init__(master, bg=COLORS["surface"], highlightthickness=1,
                         highlightbackground=COLORS["border"], **kwargs)
        self.book = book

        body = tk.Frame(self, bg=COLORS["surface"])
        body.pack(fill="both", expand=True, padx=12, pady=12)

        cover_url = book.get("cover_image")
        has_own_cover = bool(cover_url) and not is_placeholder_cover(cover_url)
        self.cover = CoverBox(body, size=image_size,
                              text="Sin imagen\nregistrada" if not has_own_cover else "Cargando imagen...")
        self.cover.pack(side="left", anchor="n")
        if has_own_cover:
            image_loader.get(cover_url, image_size, self.cover.show_photo)

        info = tk.Frame(body, bg=COLORS["surface"])
        info.pack(side="left", fill="both", expand=True, padx=(12, 0))

        title = tk.Label(info, text=book.get("title") or "(sin titulo)", bg=COLORS["surface"],
                         fg=COLORS["text"], font=FONT_H3, anchor="w", justify="left",
                         wraplength=330, cursor="hand2")
        title.pack(anchor="w")
        title.bind("<Button-1>", lambda _e: on_open(book))

        tk.Label(info, text=f"ISBN: {book.get('isbn') or '-'}", bg=COLORS["surface"],
                 fg=COLORS["muted"], font=FONT_SMALL, anchor="w").pack(anchor="w", pady=(4, 0))
        tk.Label(info, text=f"Autor: {book.get('authors') or 'Sin autor'}", bg=COLORS["surface"],
                 fg=COLORS["text"], font=FONT_SMALL, anchor="w", justify="left",
                 wraplength=330).pack(anchor="w")
        tk.Label(info, text=f"Genero: {book.get('genres') or 'General'}", bg=COLORS["surface"],
                 fg=COLORS["text"], font=FONT_SMALL, anchor="w", justify="left",
                 wraplength=330).pack(anchor="w")

        facts = tk.Frame(info, bg=COLORS["surface"])
        facts.pack(anchor="w", pady=(6, 0))
        for index, (label, value) in enumerate((
            ("Anio", book.get("year")),
            ("Precio", format_money(book.get("price"))),
            ("Existencia", book.get("stock")),
        )):
            tk.Label(facts, text=f"{label}: ", bg=COLORS["surface"], fg=COLORS["muted"],
                     font=FONT_SMALL).grid(row=0, column=index * 2, sticky="w")
            tk.Label(facts, text=str(value if value is not None else "-"), bg=COLORS["surface"],
                     fg=COLORS["text"], font=FONT_BOLD).grid(row=0, column=index * 2 + 1,
                                                             sticky="w", padx=(0, 12))

        tk.Label(info, text=f"Formato: {book.get('format_name') or '-'}   |   "
                            f"Categoria: {book.get('category_name') or '-'}",
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL,
                 anchor="w", justify="left", wraplength=330).pack(anchor="w", pady=(4, 0))

        if not has_own_cover:
            tk.Label(info, text="Este libro no tiene imagen registrada.",
                     bg=COLORS["surface"], fg=COLORS["warn"], font=FONT_SMALL,
                     anchor="w").pack(anchor="w", pady=(4, 0))

        actions = tk.Frame(info, bg=COLORS["surface"])
        actions.pack(anchor="w", pady=(8, 0))
        ttk.Button(actions, text="Ver detalle", style="Ghost.TButton",
                   command=lambda: on_open(book)).pack(side="left")
        if show_actions:
            if on_edit:
                ttk.Button(actions, text="Editar", style="Ghost.TButton",
                           command=lambda: on_edit(book)).pack(side="left", padx=(6, 0))
            if on_delete:
                ttk.Button(actions, text="Eliminar", style="Danger.TButton",
                           command=lambda: on_delete(book)).pack(side="left", padx=(6, 0))


# ==============================================================================
# Utilidades de formato
# ==============================================================================
def format_money(value):
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "-"


def format_text(value, fallback="-"): 
    if value is None or value == "":
        return fallback
    return str(value)


# ==============================================================================
# Avisos al usuario
# ==============================================================================
_ALERT_STYLE = {
    "error":   ("#B3261E", "\u2716"),   # rojo  - algo fallo
    "warning": ("#9A6700", "\u26A0"),   # ambar - atencion
    "info":    ("#1A7F37", "\u2714"),   # verde - operacion correcta
}


class AlertDialog(tk.Toplevel):
    """Aviso modal con el mismo estilo visual que el resto de la aplicacion.

    Se implementa a mano (en lugar de `tkinter.messagebox`) por dos motivos:
    el mensaje se presenta en lenguaje claro con el detalle tecnico separado,
    y el aspecto es consistente con la interfaz para las capturas de evidencia.
    """

    def __init__(self, master, title, message, kind="info", technical=None):
        super().__init__(master, bg=COLORS["surface"])
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        accent, icon = _ALERT_STYLE.get(kind, _ALERT_STYLE["info"])

        wrap = tk.Frame(self, bg=COLORS["surface"])
        wrap.pack(fill="both", expand=True, padx=20, pady=18)

        head = tk.Frame(wrap, bg=COLORS["surface"])
        head.pack(fill="x", anchor="w")
        tk.Label(head, text=icon, bg=COLORS["surface"], fg=accent,
                 font=FONT_H3).pack(side="left", padx=(0, 8))
        tk.Label(head, text=title, bg=COLORS["surface"], fg=COLORS["text"],
                 font=FONT_H3, anchor="w").pack(side="left")

        tk.Label(wrap, text=message, bg=COLORS["surface"], fg=COLORS["text"],
                 font=FONT_BASE, justify="left", anchor="w",
                 wraplength=520).pack(anchor="w", pady=(8, 0))

        if technical:
            tk.Label(wrap, text="Detalle tecnico", bg=COLORS["surface"],
                     fg=COLORS["muted"], font=FONT_SMALL,
                     anchor="w").pack(anchor="w", pady=(12, 2))
            tk.Label(wrap, text=technical, bg=COLORS["surface_alt"], fg=COLORS["text"],
                     font=FONT_MONO, justify="left", anchor="w", padx=10, pady=8,
                     wraplength=500).pack(fill="x")

        ttk.Button(wrap, text="Entendido", style="Primary.TButton",
                   command=self.destroy).pack(anchor="e", pady=(16, 0))

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self.destroy())

        self.update_idletasks()
        try:
            x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
            y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except tk.TclError:
            pass

    def show(self):
        self.grab_set()
        self.wait_window(self)


def show_error(parent, message, title="No fue posible completar la operacion", technical=None):
    """Muestra el error en lenguaje claro; el detalle tecnico va aparte."""
    AlertDialog(parent, title, message, kind="error", technical=technical).show()


def show_info(parent, message, title="Listo"):
    AlertDialog(parent, title, message, kind="info").show()


def show_warning(parent, message, title="Atencion"):
    AlertDialog(parent, title, message, kind="warning").show()


class ConfirmDialog(tk.Toplevel):
    """Confirmacion modal con el detalle de la operacion.

    Se implementa a mano (en lugar de `tkinter.messagebox`) para poder mostrar
    la peticion exacta que se enviara y para mantener el mismo estilo visual.
    Es la confirmacion previa obligatoria antes de eliminar informacion.
    """

    def __init__(self, master, title, message, detail=None,
                 confirm_text="Si, continuar", danger=True):
        super().__init__(master, bg=COLORS["surface"])
        self.result = False
        self.title(title)
        self.resizable(False, False)
        self.transient(master)

        wrap = tk.Frame(self, bg=COLORS["surface"])
        wrap.pack(fill="both", expand=True, padx=20, pady=18)

        tk.Label(wrap, text=title, bg=COLORS["surface"], fg=COLORS["text"],
                 font=FONT_H3, anchor="w").pack(anchor="w")
        tk.Label(wrap, text=message, bg=COLORS["surface"], fg=COLORS["text"], font=FONT_BASE,
                 justify="left", anchor="w", wraplength=520).pack(anchor="w", pady=(8, 0))

        if detail:
            tk.Label(wrap, text=detail, bg=COLORS["surface_alt"], fg=COLORS["text"],
                     font=FONT_MONO, justify="left", anchor="w", padx=10, pady=8,
                     wraplength=500).pack(fill="x", pady=(10, 0))

        buttons = tk.Frame(wrap, bg=COLORS["surface"])
        buttons.pack(anchor="e", pady=(16, 0))
        ttk.Button(buttons, text="Cancelar", style="Ghost.TButton",
                   command=lambda: self.answer(False)).pack(side="left")
        ttk.Button(buttons, text=confirm_text, style="Danger.TButton" if danger else "Primary.TButton",
                   command=lambda: self.answer(True)).pack(side="left", padx=(8, 0))

        self.protocol("WM_DELETE_WINDOW", lambda: self.answer(False))
        self.bind("<Escape>", lambda _e: self.answer(False))

        self.update_idletasks()
        try:
            x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
            y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except tk.TclError:
            pass

    def answer(self, value):
        self.result = bool(value)
        self.destroy()

    def show(self):
        self.grab_set()
        self.wait_window(self)
        return self.result


def confirm(parent, message, title="Confirmar accion", detail=None,
            confirm_text="Si, continuar", danger=True):
    """Pide confirmacion al usuario antes de una operacion destructiva."""
    return ConfirmDialog(parent, title, message, detail=detail,
                         confirm_text=confirm_text, danger=danger).show()
