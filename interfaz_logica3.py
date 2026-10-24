import tkinter as tk
from tkinter import ttk, messagebox

import Sistema_logica4 as sl  # debe estar en la misma carpeta

EJEMPLOS = [
    "Si nos dejan entonces nos vamos a querer toda la vida",
    "Llueve y hace frío",
    "Voy al cine o me quedo en casa",
    "No llueve",
    "Si estudio y practico entonces apruebo",
    "Si no llueve entonces voy al parque",
    "Apruebo si y solo si estudio",
    "Si hay sol o hace calor entonces voy a la alberca",
    "No es cierto que llueva y haga frío",
]

COLOR_NUEVA = "#d8f3dc"    # verde claro
COLOR_EXISTE = "#fff3bf"   # amarillo claro


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Lógica en Lenguaje Natural")
        self.geometry("1100x680")
        self.minsize(900, 560)

        self.var_frase = tk.StringVar()
        self.var_ejemplo = tk.StringVar()
        self.ultima_raiz = None  # regla principal de la última frase válida
        self._crear_widgets()
        self.entrada.focus()
        self._refrescar_biblioteca()

    # ---------------- Construcción de la ventana ----------------
    def _crear_widgets(self):
        # --- Fila de entrada ---
        top = ttk.Frame(self, padding=(12, 12, 12, 4))
        top.pack(fill="x")

        ttk.Label(top, text="Frase:").grid(row=0, column=0, sticky="w")
        self.entrada = ttk.Entry(top, textvariable=self.var_frase, font=("TkDefaultFont", 12))
        self.entrada.grid(row=0, column=1, sticky="ew", padx=8)
        self.entrada.bind("<Return>", lambda e: self.analizar())
        ttk.Button(top, text="Analizar", command=self.analizar).grid(row=0, column=2)

        ttk.Label(top, text="Ejemplos:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        combo = ttk.Combobox(top, textvariable=self.var_ejemplo, values=EJEMPLOS, state="readonly")
        combo.grid(row=1, column=1, sticky="ew", padx=8, pady=(6, 0))
        combo.bind("<<ComboboxSelected>>", self._elegir_ejemplo)
        ttk.Button(top, text="Borrar frase", command=self._borrar_frase).grid(row=1, column=2, pady=(6, 0))
        ttk.Button(top, text="Tabla de verdad", command=self.ver_tabla).grid(row=0, column=3, padx=(8, 0))
        ttk.Button(top, text="Tablas de conectivos", command=self.ver_conectivos).grid(
            row=1, column=3, padx=(8, 0), pady=(6, 0))
        top.columnconfigure(1, weight=1)

        # --- Barra de estado ---
        self.lbl_estado = ttk.Label(self, text="Escribe una frase y presiona Analizar.",
                                    padding=(12, 4), wraplength=1050)
        self.lbl_estado.pack(fill="x")

        # --- Cuerpo: resultado (izquierda) | biblioteca (derecha) ---
        cuerpo = ttk.PanedWindow(self, orient="horizontal")
        cuerpo.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        izq = ttk.LabelFrame(cuerpo, text="Resultado de la frase", padding=10)
        der = ttk.LabelFrame(cuerpo, text="Biblioteca (arreglos X y R)", padding=10)
        cuerpo.add(izq, weight=1)
        cuerpo.add(der, weight=1)

        # Resultado
        self.lbl_logica = ttk.Label(izq, text="Lógica principal: —", font=("TkDefaultFont", 12, "bold"))
        self.lbl_logica.pack(anchor="w")
        self.lbl_conectivos = ttk.Label(izq, text="Conectivos detectados: —", wraplength=470)
        self.lbl_conectivos.pack(anchor="w", pady=(4, 0))
        self.lbl_formula = ttk.Label(izq, text="Fórmula: —", wraplength=470)
        self.lbl_formula.pack(anchor="w", pady=(4, 8))

        ttk.Label(izq, text="Variables de esta frase").pack(anchor="w")
        self.tv_vars_frase = self._crear_tabla(izq, ("ref", "valor", "estado"),
                                               ("Ref", "Proposición", "Estado"), (60, 250, 150), 5)
        ttk.Label(izq, text="Reglas de esta frase").pack(anchor="w", pady=(8, 0))
        self.tv_reglas_frase = self._crear_tabla(izq, ("ref", "valor", "estado"),
                                                 ("Ref", "Regla", "Estado"), (60, 250, 150), 5)

        # Biblioteca
        ttk.Label(der, text="Variables (X)").pack(anchor="w")
        self.tv_X = self._crear_tabla(der, ("ref", "valor"), ("Ref", "Proposición"), (70, 380), 8)
        ttk.Label(der, text="Reglas (R)").pack(anchor="w", pady=(8, 0))
        self.tv_R = self._crear_tabla(der, ("ref", "regla", "formula"),
                                      ("Ref", "Regla", "Fórmula"), (60, 150, 260), 8)
        self.tv_R.bind("<ButtonRelease-1>", self._clic_regla)
        ttk.Label(der, text="Haz clic en una regla para ver su tabla de verdad.",
                  foreground="#495057").pack(anchor="w", pady=(4, 0))
        ttk.Button(der, text="Vaciar biblioteca", command=self._vaciar).pack(anchor="e", pady=(8, 0))

    def _crear_tabla(self, padre, columnas, titulos, anchos, filas):
        marco = ttk.Frame(padre)
        marco.pack(fill="both", expand=True)
        tabla = ttk.Treeview(marco, columns=columnas, show="headings", height=filas)
        for c, t, a in zip(columnas, titulos, anchos):
            tabla.heading(c, text=t)
            tabla.column(c, width=a, anchor="w")
        barra = ttk.Scrollbar(marco, orient="vertical", command=tabla.yview)
        tabla.configure(yscrollcommand=barra.set)
        tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        tabla.tag_configure("nueva", background=COLOR_NUEVA)
        tabla.tag_configure("existe", background=COLOR_EXISTE)
        return tabla

    # ---------------- Acciones ----------------
    def _elegir_ejemplo(self, _evento=None):
        self.var_frase.set(self.var_ejemplo.get())
        self.entrada.focus()

    def _clic_regla(self, evento):
        """Al hacer clic en una regla de la biblioteca, abre su tabla de verdad."""
        if self.tv_R.identify_region(evento.x, evento.y) != "cell":
            return
        fila = self.tv_R.identify_row(evento.y)
        if not fila:
            return
        ref = str(self.tv_R.item(fila, "values")[0])
        self.ver_tabla(ref)

    def _borrar_frase(self):
        self.var_frase.set("")
        self.entrada.focus()

    def _vaciar(self):
        if messagebox.askyesno("Vaciar biblioteca", "¿Borrar todas las variables y reglas guardadas?"):
            sl.X.clear()
            sl.R.clear()
            self.ultima_raiz = None
            self._limpiar_resultado()
            self._refrescar_biblioteca()
            self._estado("Biblioteca vaciada.", "#495057")

    def analizar(self):
        frase = self.var_frase.get().strip()
        if not frase:
            return
        try:
            res = sl.analizar_frase(frase)
        except sl.FraseInvalida as e:
            self._limpiar_resultado()
            self.ultima_raiz = None
            self._estado(f"✗ Frase NO válida: {e}  No se guardó ninguna variable ni regla.", "#c92a2a")
            return

        self.ultima_raiz = res["raiz"]
        info = res["info"]
        nv = sum(info["atomos"].values())
        nr = sum(info["reglas"].values())

        self.lbl_logica.config(
            text=f"Lógica principal: {sl.NOMBRES[res['principal']]} ({res['principal']})")
        self.lbl_conectivos.config(
            text="Conectivos detectados: " + ", ".join(f"{sl.NOMBRES[o]} ({o})" for o in res["usadas"]))
        self.lbl_formula.config(text=f"Fórmula: {sl.formula(res['raiz'])}")

        self._limpiar_tablas_frase()
        for ref, nueva in info["atomos"].items():
            texto = sl.X[int(ref[2:-1]) - 1]
            self.tv_vars_frase.insert("", "end", values=(ref, texto, self._estado_txt(nueva)),
                                      tags=("nueva" if nueva else "existe",))
        for ref, nueva in info["reglas"].items():
            regla = sl.R[int(ref[2:-1]) - 1]
            self.tv_reglas_frase.insert("", "end",
                                        values=(ref, "(" + ", ".join(regla) + ")", self._estado_txt(nueva)),
                                        tags=("nueva" if nueva else "existe",))

        self._refrescar_biblioteca()
        self._estado(
            f"✓ Frase válida. Variables: {nv} nueva(s), {len(info['atomos']) - nv} repetida(s). "
            f"Reglas: {nr} nueva(s), {len(info['reglas']) - nr} repetida(s).", "#2b8a3e")

    # ---------------- Tablas de verdad ----------------
    def ver_tabla(self, ref=None):
        """Muestra la tabla de verdad de `ref` (por defecto, la última frase válida)."""
        ref = ref or self.ultima_raiz
        if ref is None:
            messagebox.showinfo("Tabla de verdad", "Primero analiza una frase válida.")
            return
        try:
            atomos, reglas, filas = sl.tabla_verdad(ref)
        except ValueError as e:
            messagebox.showwarning("Tabla de verdad", str(e))
            return

        # Solo una ventana de tabla a la vez: se cierra la anterior
        if getattr(self, "_ventana_tabla", None) is not None:
            try:
                self._ventana_tabla.destroy()
            except tk.TclError:
                pass
        win = tk.Toplevel(self)
        self._ventana_tabla = win
        win.title(f"Tabla de verdad de {ref}")
        win.geometry("860x540")

        leyenda = [f"{a} = {sl.X[sl._num(a) - 1]}" for a in atomos]
        leyenda += [f"{r} = {sl.formula(r)}" for r in reglas]
        ttk.Label(win, text="\n".join(leyenda), justify="left", padding=10,
                  wraplength=820).pack(anchor="w")

        columnas = atomos + reglas
        ids = [f"c{i}" for i in range(len(columnas))]
        marco = ttk.Frame(win, padding=(10, 0))
        marco.pack(fill="both", expand=True)
        tabla = ttk.Treeview(marco, columns=ids, show="headings")
        for ident, nombre in zip(ids, columnas):
            tabla.heading(ident, text=nombre)
            tabla.column(ident, width=70, anchor="center")
        barra = ttk.Scrollbar(marco, orient="vertical", command=tabla.yview)
        tabla.configure(yscrollcommand=barra.set)
        tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        tabla.tag_configure("verdadero", background=COLOR_NUEVA)
        tabla.tag_configure("falso", background="#ffe3e3")
        for valores_a, valores_r in filas:
            valores = [sl.vf(v) for v in valores_a + valores_r]
            tabla.insert("", "end", values=valores,
                         tags=("verdadero" if valores_r[-1] else "falso",))

        ttk.Label(win, text=f"Resultado: {sl.clasificar(filas)}",
                  font=("TkDefaultFont", 11, "bold"), padding=10).pack(anchor="w")

    def ver_conectivos(self):
        win = tk.Toplevel(self)
        win.title("Tablas de verdad de los conectivos")
        for i, op in enumerate(("¬", "∧", "∨", "⇒", "⇔")):
            encabezados, filas = sl.tabla_conectivo(op)
            marco = ttk.LabelFrame(win, text=f"{sl.NOMBRES[op]} ({op})", padding=8)
            marco.grid(row=i // 3, column=i % 3, padx=8, pady=8, sticky="n")
            ids = [f"c{j}" for j in range(len(encabezados))]
            tabla = ttk.Treeview(marco, columns=ids, show="headings", height=len(filas))
            for ident, nombre in zip(ids, encabezados):
                tabla.heading(ident, text=nombre)
                tabla.column(ident, width=70, anchor="center")
            tabla.tag_configure("verdadero", background=COLOR_NUEVA)
            tabla.tag_configure("falso", background="#ffe3e3")
            for fila in filas:
                tabla.insert("", "end", values=[sl.vf(v) for v in fila],
                             tags=("verdadero" if fila[-1] else "falso",))
            tabla.pack()

    # ---------------- Utilidades ----------------
    @staticmethod
    def _estado_txt(nueva):
        return "NUEVA, guardada" if nueva else "YA EXISTÍA"

    def _estado(self, texto, color):
        self.lbl_estado.config(text=texto, foreground=color)

    def _limpiar_tablas_frase(self):
        for tabla in (self.tv_vars_frase, self.tv_reglas_frase):
            tabla.delete(*tabla.get_children())

    def _limpiar_resultado(self):
        self.lbl_logica.config(text="Lógica principal: —")
        self.lbl_conectivos.config(text="Conectivos detectados: —")
        self.lbl_formula.config(text="Fórmula: —")
        self._limpiar_tablas_frase()

    def _refrescar_biblioteca(self):
        self.tv_X.delete(*self.tv_X.get_children())
        self.tv_R.delete(*self.tv_R.get_children())
        for i, a in enumerate(sl.X, 1):
            self.tv_X.insert("", "end", values=(f"X[{i}]", a))
        for i, r in enumerate(sl.R, 1):
            self.tv_R.insert("", "end",
                             values=(f"R[{i}]", "(" + ", ".join(r) + ")", sl.formula(f"R[{i}]")))


if __name__ == "__main__":
    App().mainloop()
