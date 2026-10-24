import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog

from parser_nl import Biblioteca, texto_formula, es_literal, letras_de
from tableau import (Tableau, ArbolDemasiadoGrande, disenar, formatear_asignacion,
                     PALABRA_INCONSISTENTE)

EJEMPLOS = {
    "Dragón, caballero y princesa (satisfacible)": (
        "Si hay dragón entonces el caballero usa la espada\n"
        "Si el caballero usa la espada entonces la princesa se salva\n"
        "Hay dragón"
    ),
    "Base inconsistente (todas las ramas se cierran)": (
        "Si hay dragón entonces el caballero usa la espada\n"
        "Si el caballero usa la espada entonces la princesa se salva\n"
        "Hay dragón\n"
        "No es cierto que la princesa se salva"
    ),
    "Varias soluciones (ramas abiertas)": (
        "El dragón duerme o el caballero ataca\n"
        "Si el caballero ataca entonces la princesa huye\n"
        "El dragón duerme si y solo si no hay fuego\n"
        "Es de día"
    ),
    "Pizarrón de la clase": (
        "Si nos dejan entonces nos vamos a querer toda la vida\n"
        "Nos dejan"
    ),
}

VERDE, VERDE_CLARO = "#2b8a3e", "#d8f3dc"
ROJO, ROJO_CLARO = "#c92a2a", "#ffe3e3"
AMARILLO_CLARO = "#fff3bf"
EST_NUEVA, EST_EXISTE = "NUEVA, guardada", "YA EXISTÍA"
VISTA_SEPARADAS = "Cada regla por separado"
VISTA_BASE = "Base completa (todas las reglas a la vez)"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Base de conocimiento y árbol semántico")
        self.geometry("1360x800")
        self.minsize(1050, 620)

        self.fuente = tkfont.nametofont("TkFixedFont").copy()
        self.fuente.configure(size=10)
        self.fuente_peq = tkfont.nametofont("TkFixedFont").copy()
        self.fuente_peq.configure(size=8)
        self.fuente_neg = tkfont.nametofont("TkFixedFont").copy()
        self.fuente_neg.configure(size=11, weight="bold")

        self.biblio = Biblioteca()       # variables y reglas guardadas mientras el programa está abierto
        self._atomos_tocados = {}        # letra -> True (NUEVA) / False (YA EXISTÍA) en el último análisis
        self._reglas_tocadas = {}        # índice de regla -> True / False
        self._errores = []               # líneas inválidas del último análisis
        self.var_ejemplo = tk.StringVar()
        self.var_vista = tk.StringVar(value=VISTA_SEPARADAS)
        self.arboles = []        # [("R1", formula, Tableau de ESA regla), ...]
        self.base_tab = None     # Tableau con todas las reglas a la vez
        self._crear_widgets()
        self._estado("Escribe reglas y hechos (uno por línea) y presiona Analizar. "
                     "Lo válido se guarda en la biblioteca.", "#495057")

    # ---------------- Construcción de la ventana ----------------
    def _crear_widgets(self):
        cuerpo = ttk.PanedWindow(self, orient="horizontal")
        cuerpo.pack(fill="both", expand=True, padx=8, pady=8)
        izq = ttk.Frame(cuerpo)
        der = ttk.Frame(cuerpo)
        cuerpo.add(izq, weight=3)
        cuerpo.add(der, weight=5)

        # --- Izquierda: entrada y biblioteca ---
        marco = ttk.LabelFrame(izq, text="Reglas y hechos nuevos (una por línea)", padding=6)
        marco.pack(fill="x")
        caja = ttk.Frame(marco)
        caja.pack(fill="x")
        self.txt = tk.Text(caja, height=8, wrap="word", font=("TkDefaultFont", 11), undo=True)
        barra = ttk.Scrollbar(caja, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=barra.set)
        self.txt.pack(side="left", fill="x", expand=True)
        barra.pack(side="right", fill="y")
        self.txt.tag_configure("error", background=ROJO_CLARO)
        self.txt.bind("<Control-Return>", lambda e: (self.analizar(), "break")[1])

        fila = ttk.Frame(marco)
        fila.pack(fill="x", pady=(6, 0))
        ttk.Button(fila, text="Analizar (Ctrl+Enter)", command=self.analizar).pack(side="left")
        ttk.Button(fila, text="Limpiar texto", command=lambda: self.txt.delete("1.0", "end")).pack(side="left", padx=6)
        ttk.Button(fila, text="Vaciar biblioteca", command=self._vaciar_biblioteca).pack(side="left")
        combo = ttk.Combobox(marco, textvariable=self.var_ejemplo, values=list(EJEMPLOS), state="readonly")
        combo.pack(fill="x", pady=(6, 0))
        combo.set("Cargar un ejemplo (reemplaza la biblioteca)…")
        combo.bind("<<ComboboxSelected>>", self._elegir_ejemplo)
        fila = ttk.Frame(marco)
        fila.pack(fill="x", pady=(6, 0))
        ttk.Button(fila, text="Guardar biblioteca…", command=self._guardar_archivo).pack(side="left")
        ttk.Button(fila, text="Cargar biblioteca…", command=self._cargar_archivo).pack(side="left", padx=6)

        marco = ttk.LabelFrame(izq, text="Tabla de átomos (variables guardadas)", padding=6)
        marco.pack(fill="both", expand=True, pady=(8, 0))
        self.tv_atomos = self._tabla(marco, ("letra", "significado", "estado"),
                                     ("Letra", "Significado", "Estado"), (50, 230, 110), 6)

        marco = ttk.LabelFrame(izq, text="Reglas guardadas y sus fórmulas", padding=6)
        marco.pack(fill="both", expand=True, pady=(8, 0))
        self.tv_reglas = self._tabla(marco, ("regla", "tipo", "formula", "estado", "texto"),
                                     ("Regla", "Tipo", "Fórmula", "Estado", "Texto original"),
                                     (45, 50, 105, 105, 220), 7)
        for tabla in (self.tv_atomos, self.tv_reglas):
            tabla.tag_configure("nueva", background=VERDE_CLARO)
            tabla.tag_configure("existe", background=AMARILLO_CLARO)
            tabla.tag_configure("error", background=ROJO_CLARO)
        self.tv_reglas.bind("<<TreeviewSelect>>", self._seleccion_regla)
        ttk.Button(marco, text="Eliminar regla seleccionada", command=self._eliminar_regla).pack(anchor="e", pady=(6, 0))

        # --- Derecha: pestañas ---
        self.libreta = ttk.Notebook(der)
        self.libreta.pack(fill="both", expand=True)

        pestana_arbol = ttk.Frame(self.libreta)
        self.libreta.add(pestana_arbol, text="Árbol semántico")
        ttk.Label(
            pestana_arbol, padding=(8, 6),
            text="✓n = fórmula desarrollada en el paso n     ✕ rama cerrada (rojo)     ○ rama abierta (verde)",
        ).pack(anchor="w")
        fila_vista = ttk.Frame(pestana_arbol)
        fila_vista.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(fila_vista, text="Mostrar:").pack(side="left")
        self.combo_vista = ttk.Combobox(fila_vista, textvariable=self.var_vista, state="readonly", width=70)
        self.combo_vista.pack(side="left", padx=6)
        self.combo_vista.bind("<<ComboboxSelected>>", lambda e: self._redibujar())
        zona = ttk.Frame(pestana_arbol)
        zona.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(zona, background="white", highlightthickness=0)
        sb_v = ttk.Scrollbar(zona, orient="vertical", command=self.canvas.yview)
        sb_h = ttk.Scrollbar(zona, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        sb_v.pack(side="right", fill="y")
        sb_h.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120 or (1 if e.delta > 0 else -1)), "units"))
        self.canvas.bind("<Shift-MouseWheel>", lambda e: self.canvas.xview_scroll(-1 * (e.delta // 120 or (1 if e.delta > 0 else -1)), "units"))
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        self.txt_resultado = self._texto_solo_lectura("Resultado")
        self.txt_pasos = self._texto_solo_lectura("Pasos del tableau")

        self.lbl_estado = ttk.Label(self, padding=(10, 4), text="", wraplength=1300)
        self.lbl_estado.pack(fill="x")

    def _tabla(self, padre, columnas, titulos, anchos, filas):
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
        return tabla

    def _texto_solo_lectura(self, titulo):
        pestana = ttk.Frame(self.libreta)
        self.libreta.add(pestana, text=titulo)
        texto = tk.Text(pestana, wrap="word", font=("TkDefaultFont", 11), padx=10, pady=8, state="disabled")
        barra = ttk.Scrollbar(pestana, orient="vertical", command=texto.yview)
        texto.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        texto.pack(side="left", fill="both", expand=True)
        texto.tag_configure("titulo", font=("TkDefaultFont", 13, "bold"))
        texto.tag_configure("bien", foreground=VERDE, font=("TkDefaultFont", 12, "bold"))
        texto.tag_configure("mal", foreground=ROJO, font=("TkDefaultFont", 12, "bold"))
        texto.tag_configure("mono", font=self.fuente)
        texto.tag_configure("regla", font=("TkDefaultFont", 11, "bold"))
        return texto

    # ---------------- Acciones ----------------
    def analizar(self):
        """Guarda en la biblioteca lo válido del cuadro de texto y recalcula el árbol."""
        self.txt.tag_remove("error", "1.0", "end")
        res = self.biblio.agregar(self.txt.get("1.0", "end"))
        self._atomos_tocados = res.atomos
        self._reglas_tocadas = res.reglas
        self._errores = res.errores
        for l in res.errores:
            self.txt.tag_add("error", f"{l.numero}.0", f"{l.numero}.end")
        self._recalcular(con_resumen=True)

    def _recalcular(self, con_resumen=False):
        """Redibuja tablas, árbol y resultado a partir de la biblioteca."""
        self._mostrar_tablas()
        self._vaciar_resultados()
        resumen = ""
        if con_resumen:
            na = sum(self._atomos_tocados.values())
            nr = sum(self._reglas_tocadas.values())
            resumen = (f"Variables: {na} nueva(s), {len(self._atomos_tocados) - na} ya existía(n). "
                       f"Reglas: {nr} nueva(s), {len(self._reglas_tocadas) - nr} ya existía(n).  ")

        if self._errores:
            lineas = "\n".join(f"  Línea {l.numero}: {l.error}" for l in self._errores)
            self._escribir(self.txt_resultado, [
                ("Hay frases no válidas\n", "mal"),
                ("De esas líneas no se guardó ninguna variable ni regla. "
                 "Corrígelas (están marcadas en rojo) y vuelve a analizar.\n\n" + lineas + "\n", None)])
            self.libreta.select(self.txt_resultado.master)
            self._estado(f"✗ {resumen}{len(self._errores)} línea(s) no válida(s): no se guardaron y "
                         "el árbol no se calcula hasta corregirlas.", ROJO)
            return
        if not self.biblio.reglas:
            self._estado("La biblioteca está vacía. Escribe reglas o hechos y presiona Analizar.", "#495057")
            return

        reglas = self.biblio.reglas_para_tableau()
        self.arboles = [(et, f, Tableau([(et, f)])) for et, f in reglas]     # uno por regla, sin mezclar
        try:
            self.base_tab = Tableau(reglas)                                   # todas las reglas a la vez
            aviso_base = ""
        except ArbolDemasiadoGrande as e:
            self.base_tab, aviso_base = None, str(e)

        self._actualizar_vistas()
        self._redibujar()
        self._mostrar_resultado(aviso_base)
        self._escribir_pasos(aviso_base)
        self.libreta.select(self.canvas.master.master)
        if self.base_tab is None:
            self._estado(f"✓ {resumen}Árbol de cada regla listo. Base completa: {aviso_base}", ROJO)
        elif self.base_tab.satisfacible:
            self._estado(f"✓ {resumen}Base completa satisfacible: "
                         f"{len(self.base_tab.ramas_abiertas())} rama(s) abierta(s).", VERDE)
        else:
            self._estado(f"✓ {resumen}En la base completa todas las ramas se cierran: "
                         f"la base es {PALABRA_INCONSISTENTE}.", ROJO)

    def _actualizar_vistas(self):
        opciones = [VISTA_SEPARADAS, VISTA_BASE] + [f"{et}: {texto_formula(f)}" for et, f, _ in self.arboles]
        self.combo_vista.configure(values=opciones)
        if self.var_vista.get() not in opciones:
            self.var_vista.set(VISTA_SEPARADAS)

    def _seleccion_regla(self, _evento=None):
        """Al seleccionar una regla en la tabla se muestra SOLO su árbol."""
        seleccion = self.tv_reglas.selection()
        if not seleccion or not str(seleccion[0]).startswith("r"):
            return
        idx = int(str(seleccion[0])[1:])
        if idx >= len(self.arboles):
            return
        et, f, _ = self.arboles[idx]
        self.var_vista.set(f"{et}: {texto_formula(f)}")
        self._redibujar()
        self.libreta.select(self.canvas.master.master)

    def _elegir_ejemplo(self, _evento=None):
        nombre = self.var_ejemplo.get()
        if nombre not in EJEMPLOS:
            return
        self.biblio.vaciar()
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", EJEMPLOS[nombre])
        self.analizar()

    def _vaciar_biblioteca(self):
        if self.biblio.reglas or self.biblio.atomos:
            if not messagebox.askyesno("Vaciar biblioteca", "¿Borrar todas las variables y reglas guardadas?"):
                return
        self.biblio.vaciar()
        self._atomos_tocados, self._reglas_tocadas, self._errores = {}, {}, []
        self.txt.tag_remove("error", "1.0", "end")
        self._recalcular()
        self._estado("Biblioteca vaciada.", "#495057")

    def _eliminar_regla(self):
        seleccion = self.tv_reglas.selection()
        if not seleccion or not str(seleccion[0]).startswith("r"):
            messagebox.showinfo("Eliminar regla", "Selecciona primero una regla de la tabla.")
            return
        idx = int(str(seleccion[0])[1:])
        self.biblio.eliminar_regla(idx)
        self._atomos_tocados, self._reglas_tocadas, self._errores = {}, {}, []
        self._recalcular()
        self._estado(f"Regla R{idx + 1} eliminada. Si su texto sigue en el cuadro de escritura, "
                     "bórralo o se volverá a guardar al analizar.", "#495057")

    def _guardar_archivo(self):
        ruta = filedialog.asksaveasfilename(defaultextension=".json", initialfile="biblioteca.json",
                                            filetypes=[("Biblioteca (JSON)", "*.json")])
        if not ruta:
            return
        try:
            self.biblio.guardar(ruta)
        except OSError as e:
            messagebox.showerror("Guardar biblioteca", f"No se pudo guardar el archivo:\n{e}")
            return
        self._estado(f"Biblioteca guardada en {ruta}", VERDE)

    def _cargar_archivo(self):
        ruta = filedialog.askopenfilename(filetypes=[("Biblioteca (JSON)", "*.json")])
        if not ruta:
            return
        try:
            self.biblio.cargar(ruta)
        except (OSError, ValueError, KeyError, TypeError) as e:
            messagebox.showerror("Cargar biblioteca", f"No se pudo leer el archivo:\n{e}")
            return
        self._atomos_tocados, self._reglas_tocadas, self._errores = {}, {}, []
        self._recalcular()
        self._estado(f"Biblioteca cargada desde {ruta}", VERDE)

    # ---------------- Presentación ----------------
    @staticmethod
    def _estado_y_tag(marca):
        if marca is True:
            return EST_NUEVA, ("nueva",)
        if marca is False:
            return EST_EXISTE, ("existe",)
        return "", ()

    def _mostrar_tablas(self):
        self.tv_atomos.delete(*self.tv_atomos.get_children())
        self.tv_reglas.delete(*self.tv_reglas.get_children())
        for letra, significado in self.biblio.atomos:
            estado, tags = self._estado_y_tag(self._atomos_tocados.get(letra))
            self.tv_atomos.insert("", "end", values=(letra, significado, estado), tags=tags)
        for i, r in enumerate(self.biblio.reglas):
            estado, tags = self._estado_y_tag(self._reglas_tocadas.get(i))
            tipo = "Hecho" if es_literal(r["formula"]) else "Regla"
            self.tv_reglas.insert("", "end", iid=f"r{i}", tags=tags,
                                  values=(f"R{i + 1}", tipo, texto_formula(r["formula"]), estado, r["texto"]))
        for l in self._errores:
            self.tv_reglas.insert("", "end", tags=("error",),
                                  values=("—", f"Línea {l.numero}", "no válida", "NO se guardó", l.original))

    def _mostrar_resultado(self, aviso_base=""):
        letras = self.biblio.letras
        partes = [("Cada regla tiene su propio árbol; al final se combinan todas.\n\n", None),
                  ("Cada regla por separado\n", "titulo")]
        for et, f, tab in self.arboles:
            propias = set(letras_de(f))
            ls = [l for l in letras if l in propias]
            abiertas, total = tab.ramas_abiertas(), len(tab.hojas())
            partes.append((f"\n{et}:  {texto_formula(f)}\n", "regla"))
            if abiertas:
                partes.append((f"{len(abiertas)} rama(s) abierta(s) y {total - len(abiertas)} cerrada(s). "
                               "Se cumple cuando:\n", None))
                for i, h in enumerate(abiertas, 1):
                    partes.append((f"   Rama abierta {i}:  {formatear_asignacion(tab.asignacion(h), ls)}\n", "mono"))
            else:
                partes.append(("Todas las ramas se cierran: por sí sola esta regla es "
                               f"{PALABRA_INCONSISTENTE}.\n", "mal"))

        partes.append(("\nBase completa (todas las reglas a la vez)\n", "titulo"))
        partes.append((f"Base de conocimiento: {len(self.biblio.reglas)} regla(s)/hecho(s), "
                       f"{len(self.biblio.atomos)} proposición(es) simple(s). "
                       "Se suponen verdaderas todas las reglas.\n\n", None))
        tab = self.base_tab
        if tab is None:
            partes.append((aviso_base + "\n", "mal"))
        else:
            abiertas, total = tab.ramas_abiertas(), len(tab.hojas())
            if not abiertas:
                partes += [(f"Todas las ramas se cierran ({total} de {total}): "
                            f"la base de conocimiento es {PALABRA_INCONSISTENTE}.\n", "mal"),
                           ("No existe ninguna asignación de V/F que haga verdaderas todas las reglas a la vez.\n", None)]
            else:
                partes += [(f"{len(abiertas)} rama(s) abierta(s) y {total - len(abiertas)} cerrada(s): "
                            "la base de conocimiento es satisfacible.\n", "bien"),
                           ("Condiciones en las que todas las reglas se cumplen (una línea por rama abierta):\n\n", None)]
                for i, h in enumerate(abiertas, 1):
                    partes.append((f"  Rama abierta {i}:  {formatear_asignacion(tab.asignacion(h), letras)}\n", "mono"))
                partes.append(("\nUna letra con «V o F» no está fijada por esa rama: puede tomar cualquiera de los dos valores.\n", None))
        self._escribir(self.txt_resultado, partes)

    def _escribir_pasos(self, aviso_base=""):
        partes = []
        for et, f, tab in self.arboles:
            partes += [(f"══ {et}: {texto_formula(f)} ══\n", "regla"), ("\n".join(tab.pasos) + "\n\n", None)]
        partes.append(("══ Base completa ══\n", "regla"))
        partes.append((("\n".join(self.base_tab.pasos) if self.base_tab else aviso_base) + "\n", None))
        self._escribir(self.txt_pasos, partes)

    def _vaciar_resultados(self):
        self.arboles, self.base_tab = [], None
        self.canvas.delete("all")
        self._escribir(self.txt_resultado, [])
        self._escribir(self.txt_pasos, [])

    def _escribir(self, widget, partes):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        for texto, etiqueta in partes:
            widget.insert("end", texto, etiqueta) if etiqueta else widget.insert("end", texto)
        widget.configure(state="disabled")

    def _estado(self, texto, color):
        self.lbl_estado.configure(text=texto, foreground=color)

    # ---------------- Dibujo de los árboles ----------------
    def _titulo(self, etiqueta, formula, tab):
        ab = len(tab.ramas_abiertas())
        return (f"{etiqueta}:  {texto_formula(formula)}      —      "
                f"{ab} rama(s) abierta(s), {len(tab.hojas()) - ab} cerrada(s)")

    def _redibujar(self):
        """Dibuja según la vista elegida: cada regla por separado, una sola regla o la base completa."""
        c = self.canvas
        c.delete("all")
        if not self.arboles:
            return
        vista = self.var_vista.get()
        if vista == VISTA_BASE:
            if self.base_tab is None:
                c.create_text(20, 20, anchor="nw", font=self.fuente_neg, fill=ROJO,
                              text="El árbol de la base completa es demasiado grande para dibujarse.")
                return
            todas = " ∧ ".join(f"{et}" for et, _, _ in self.arboles)
            ab = len(self.base_tab.ramas_abiertas())
            grupos = [(f"Base completa ({todas} verdaderas a la vez)      —      "
                       f"{ab} rama(s) abierta(s), {len(self.base_tab.hojas()) - ab} cerrada(s)", self.base_tab)]
        elif vista == VISTA_SEPARADAS:
            grupos = [(self._titulo(et, f, t), t) for et, f, t in self.arboles]
        else:
            et_elegida = vista.split(":")[0]
            grupos = [(self._titulo(et, f, t), t) for et, f, t in self.arboles if et == et_elegida]

        y, ancho, separadores = 0, 0, []
        for titulo, tab in grupos:
            c.create_text(14, y + 20, anchor="w", text=titulo, font=self.fuente_neg, fill="#212529")
            w, h = self._dibujar(tab, dy=y + 40)
            ancho = max(ancho, w, 14 + self.fuente_neg.measure(titulo) + 20)
            y += 40 + h + 16
            separadores.append(y - 8)
        for sy in separadores[:-1]:
            c.create_line(0, sy, ancho, sy, fill="#ced4da", dash=(4, 4))
        c.configure(scrollregion=(0, 0, ancho, y))
        c.xview_moveto(0)
        c.yview_moveto(0)

    def _dibujar(self, tab, dx=0, dy=0):
        """Dibuja un árbol con su esquina en (dx, dy). Devuelve (ancho, alto) que ocupa."""
        c = self.canvas
        dis = disenar(tab, medir=self.fuente.measure)
        pos, abierto = dis["pos"], dis["abierto"]

        for n in tab.nodos:                       # primero las líneas
            if n.padre is not None:
                px, py, _, ph = pos[n.padre.id]
                cx, cy, _, _ = pos[n.id]
                c.create_line(dx + px, dy + py + ph, dx + cx, dy + cy,
                              fill=VERDE if abierto[n.id] else ROJO, width=2)

        for n in tab.nodos:                       # luego las cajas
            x, y, w, h = pos[n.id]
            x, y = dx + x, dy + y
            hoja = not n.hijos
            if hoja and n.cerrada:
                relleno, borde = ROJO_CLARO, ROJO
            elif hoja:
                relleno, borde = VERDE_CLARO, VERDE
            else:
                relleno, borde = "white", "#868e96"
            c.create_rectangle(x - w / 2, y, x + w / 2, y + h, fill=relleno, outline=borde, width=2)
            l1, l2 = dis["lineas"][n.id]
            c.create_text(x, y + 15, text=l1, font=self.fuente, fill="#212529")
            c.create_text(x, y + 34, text=l2, font=self.fuente_peq, fill="#868e96")
            if hoja and n.cerrada:
                letra = n.contradiccion[0]
                c.create_text(x, y + h + 16, text=f"✕  {letra} y ¬{letra}", font=self.fuente_neg, fill=ROJO)
            elif hoja:
                c.create_text(x, y + h + 16, text="○  abierta", font=self.fuente_neg, fill=VERDE)
        return dis["ancho"], dis["alto"]


if __name__ == "__main__":
    App().mainloop()
