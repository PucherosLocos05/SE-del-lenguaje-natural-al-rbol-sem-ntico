"""Tableau semántico (árbol semántico) para una base de conocimiento.

Se parte suponiendo que TODAS las reglas son verdaderas y se desarrolla cada fórmula
en las ramas que tiene debajo, hasta quedar solo letras o letras negadas.
"""
from parser_nl import texto_formula

MAX_NODOS = 1500
PALABRA_INCONSISTENTE = "INSATISFACIBLE (inconsistente)"   # cámbiala si tu profe usa otro término


class ArbolDemasiadoGrande(Exception):
    pass


# ---------------- Reglas de expansión ----------------
def neg(f):
    return ("not", f)


def literal(f):
    """(letra, positivo?) si es una letra o letra negada; si no, None."""
    if f[0] == "var":
        return (f[1], True)
    if f[0] == "not" and f[1][0] == "var":
        return (f[1][1], False)
    return None


def expansion(f):
    """Regla que se aplica a `f`: (tipo, nombre, ramas) o None si f es un literal.
    tipo = "alfa" (no ramifica) o "beta" (ramifica). Cada rama es una lista de fórmulas."""
    t = f[0]
    if t == "and":                                  # A ∧ B  ->  A, B
        return ("alfa", "∧", [[f[1], f[2]]])
    if t == "or":                                   # A ∨ B  ->  A | B
        return ("beta", "∨", [[f[1]], [f[2]]])
    if t == "imp":                                  # A → B  ->  ¬A | B
        return ("beta", "→", [[neg(f[1])], [f[2]]])
    if t == "iff":                                  # A ↔ B  ->  A, B | ¬A, ¬B
        return ("beta", "↔", [[f[1], f[2]], [neg(f[1]), neg(f[2])]])
    if t == "not":
        g = f[1]
        u = g[0]
        if u == "var":
            return None
        if u == "not":                              # ¬¬A  ->  A
            return ("alfa", "¬¬", [[g[1]]])
        if u == "or":                               # ¬(A ∨ B)  ->  ¬A, ¬B
            return ("alfa", "¬∨", [[neg(g[1]), neg(g[2])]])
        if u == "imp":                              # ¬(A → B)  ->  A, ¬B
            return ("alfa", "¬→", [[g[1], neg(g[2])]])
        if u == "and":                              # ¬(A ∧ B)  ->  ¬A | ¬B
            return ("beta", "¬∧", [[neg(g[1])], [neg(g[2])]])
        if u == "iff":                              # ¬(A ↔ B)  ->  A, ¬B | ¬A, B
            return ("beta", "¬↔", [[g[1], neg(g[2])], [neg(g[1]), g[2]]])
    return None


# ---------------- Árbol ----------------
class Nodo:
    def __init__(self, id_, formula, origen, padre):
        self.id = id_
        self.formula = formula
        self.origen = origen          # "R1" o "de 3 (∧)"
        self.padre = padre
        self.hijos = []
        self.aplicada = None          # número de paso en que se desarrolló (✓)
        self.cerrada = False          # hoja cerrada (✕)
        self.contradiccion = None     # (letra, id de la letra, id de la letra negada)

    @property
    def texto(self):
        return texto_formula(self.formula)


class Tableau:
    def __init__(self, reglas):
        """reglas: [("R1", formula), ...]  (todas se suponen verdaderas)."""
        if not reglas:
            raise ValueError("La base de conocimiento está vacía.")
        self.nodos = []
        self.raiz = None
        self.pasos = []
        ultimo = None
        for etiqueta, f in reglas:
            ultimo = self._nuevo(f, etiqueta, ultimo)
        self.pasos.append("Se parte suponiendo verdaderas todas las reglas: "
                          + ", ".join(f"{e}: {texto_formula(f)}" for e, f in reglas) + ".")
        if self._revisar_cierre(ultimo):
            self.pasos.append(self._texto_cierre(ultimo))
        self._expandir()

    # ----- construcción -----
    def _nuevo(self, formula, origen, padre):
        if len(self.nodos) >= MAX_NODOS:
            raise ArbolDemasiadoGrande(
                f"El árbol supera {MAX_NODOS} nodos; simplifica la base de conocimiento.")
        nodo = Nodo(len(self.nodos) + 1, formula, origen, padre)
        self.nodos.append(nodo)
        if padre is None:
            self.raiz = nodo
        else:
            padre.hijos.append(nodo)
        return nodo

    def camino(self, nodo):
        ruta = []
        while nodo is not None:
            ruta.append(nodo)
            nodo = nodo.padre
        return ruta[::-1]

    def _revisar_cierre(self, hoja):
        """Cierra la hoja si su rama contiene una letra y su negación."""
        vistos = {}
        for n in self.camino(hoja):
            lit = literal(n.formula)
            if lit is None:
                continue
            letra, positivo = lit
            if (letra, not positivo) in vistos:
                otro = vistos[(letra, not positivo)]
                ids = (n.id, otro) if positivo else (otro, n.id)
                hoja.cerrada = True
                hoja.contradiccion = (letra, ids[0], ids[1])
                return True
            vistos.setdefault((letra, positivo), n.id)
        return False

    def _texto_cierre(self, hoja):
        letra, a, b = hoja.contradiccion
        return f"   ✕ Se cierra la rama que termina en n{hoja.id}: {letra} (n{a}) y ¬{letra} (n{b})."

    def _hojas_bajo(self, nodo, solo_abiertas):
        res, pila = [], [nodo]
        while pila:
            n = pila.pop()
            if n.hijos:
                pila.extend(reversed(n.hijos))
            elif not (solo_abiertas and n.cerrada):
                res.append(n)
        return res

    def _elegir(self):
        """Siguiente fórmula a desarrollar: primero las que no ramifican."""
        primera_beta = None
        for n in self.nodos:
            if n.aplicada is not None or literal(n.formula) is not None:
                continue
            if not self._hojas_bajo(n, True):
                continue          # todas sus ramas ya están cerradas
            if expansion(n.formula)[0] == "alfa":
                return n
            if primera_beta is None:
                primera_beta = n
        return primera_beta

    def _expandir(self):
        paso = 0
        while True:
            n = self._elegir()
            if n is None:
                break
            paso += 1
            tipo, nombre, ramas = expansion(n.formula)
            n.aplicada = paso
            hojas = self._hojas_bajo(n, True)
            if tipo == "alfa":
                aporta = ", ".join(texto_formula(f) for f in ramas[0])
                desc = f"agrega {aporta}"
            else:
                desc = "ramifica en " + " | ".join(
                    "[" + ", ".join(texto_formula(f) for f in r) + "]" for r in ramas)
            donde = "en la rama abierta" if len(hojas) == 1 else f"en las {len(hojas)} ramas abiertas"
            self.pasos.append(f"Paso {paso}: regla {nombre} sobre n{n.id} «{n.texto}» → {desc} ({donde}).")
            for hoja in hojas:
                for rama in ramas:
                    ultimo = hoja
                    for f in rama:
                        ultimo = self._nuevo(f, f"de {n.id} ({nombre})", ultimo)
                    if self._revisar_cierre(ultimo):
                        self.pasos.append(self._texto_cierre(ultimo))
        total = len(self.hojas())
        abiertas = len(self.ramas_abiertas())
        self.pasos.append(f"Fin: solo quedan letras o letras negadas. {abiertas} rama(s) abierta(s) "
                          f"y {total - abiertas} cerrada(s).")

    # ----- resultados -----
    def hojas(self):
        return self._hojas_bajo(self.raiz, False)

    def ramas_abiertas(self):
        return self._hojas_bajo(self.raiz, True)

    @property
    def satisfacible(self):
        return bool(self.ramas_abiertas())

    def asignacion(self, hoja):
        """{'p': True, 'q': False} con los literales de la rama que termina en `hoja`."""
        asig = {}
        for n in self.camino(hoja):
            lit = literal(n.formula)
            if lit:
                asig[lit[0]] = lit[1]
        return asig


def formatear_asignacion(asig, letras):
    """'p = V, q = F, r = V o F' (las letras que la rama no fija pueden valer V o F)."""
    partes = []
    for l in letras:
        if l in asig:
            partes.append(f"{l} = {'V' if asig[l] else 'F'}")
        else:
            partes.append(f"{l} = V o F")
    return ", ".join(partes)


# ---------------- Diseño visual (coordenadas del árbol) ----------------
def disenar(tab, medir=None, alto=46, sep_v=30, sep_h=26, min_w=84, pad=20, margen=30):
    """Calcula la posición de cada nodo. `medir(texto)` devuelve el ancho en píxeles."""
    medir = medir or (lambda s: 8 * len(s))
    lineas, caja = {}, {}
    for n in tab.nodos:
        l1 = f"{n.id}. {n.texto}" + (f"  ✓{n.aplicada}" if n.aplicada else "")
        l2 = n.origen
        lineas[n.id] = (l1, l2)
        caja[n.id] = max(min_w, medir(l1) + pad, medir(l2) + pad)

    ancho_sub, abierto = {}, {}
    for n in reversed(tab.nodos):          # los hijos siempre se crean después del padre
        total = sum(ancho_sub[h.id] for h in n.hijos) + sep_h * max(len(n.hijos) - 1, 0)
        ancho_sub[n.id] = max(caja[n.id], total)
        abierto[n.id] = (not n.cerrada) if not n.hijos else any(abierto[h.id] for h in n.hijos)

    pos, tramo, prof_max = {}, {}, 0
    pila = [(tab.raiz, margen, 0)]
    while pila:
        n, x0, d = pila.pop()
        prof_max = max(prof_max, d)
        W = ancho_sub[n.id]
        tramo[n.id] = (x0, W)
        if n.hijos:
            total = sum(ancho_sub[h.id] for h in n.hijos) + sep_h * (len(n.hijos) - 1)
            x = x0 + (W - total) / 2
            centros = []
            for h in n.hijos:
                pila.append((h, x, d + 1))
                centros.append(x + ancho_sub[h.id] / 2)
                x += ancho_sub[h.id] + sep_h
            cx = (centros[0] + centros[-1]) / 2
        else:
            cx = x0 + W / 2
        pos[n.id] = (cx, margen + d * (alto + sep_v), caja[n.id], alto)

    # Un nodo con un solo hijo se alinea con él (línea recta), si su caja cabe en su tramo
    for n in reversed(tab.nodos):
        if len(n.hijos) == 1:
            cx = pos[n.hijos[0].id][0]
            _, y, w, h = pos[n.id]
            x0, W = tramo[n.id]
            if cx - w / 2 >= x0 and cx + w / 2 <= x0 + W:
                pos[n.id] = (cx, y, w, h)

    return {
        "pos": pos, "lineas": lineas, "abierto": abierto,
        "ancho": ancho_sub[tab.raiz.id] + 2 * margen,
        "alto": margen + (prof_max + 1) * (alto + sep_v) + 50,
    }
