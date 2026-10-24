"""Parser: reglas y hechos en español -> fórmulas lógicas con letras (p, q, r...).

Fórmulas (tuplas):
    ("var", "p")            proposición simple
    ("not", A)              ¬A
    ("and", A, B)           A ∧ B
    ("or",  A, B)           A ∨ B
    ("imp", A, B)           A → B
    ("iff", A, B)           A ↔ B
"""
import re

SIMBOLOS = {"and": "∧", "or": "∨", "imp": "→", "iff": "↔"}
LETRAS = list("pqrstuvwxyzabcdefghijklmno")

# El orden importa: del conectivo de menor precedencia al de mayor.
PATRONES = [
    ("iff", r"^(.+?),? (?:si y s[oó]lo si|sii|cuando y s[oó]lo cuando|es equivalente a|equivale a) (.+)$"),
    ("imp", r"^si (.+?),? entonces (.+)$"),
    ("imp", r"^(.+?) implica (.+)$"),
    ("not", r"^(?:no es cierto que|es falso que) (.+)$"),   # negación de alcance amplio
    ("or",  r"^o bien (.+?),? o (.+)$"),
    ("or",  r"^(.+?) o (.+)$"),
    ("and", r"^tanto (.+?) como (.+)$"),
    ("and", r"^(.+?) (?:y|pero|adem[aá]s) (.+)$"),
    ("not", r"^no (.+)$"),                                   # negación simple
]

# Palabras de conectivos que NO deben quedar dentro de una proposición simple
SOBRANTES = {"si", "entonces", "implica", "y", "o", "pero", "además", "ademas", "tanto", "sii"}


class ErrorFrase(Exception):
    pass


# ---------------- Utilidades de texto ----------------
def sin_acentos(texto):
    return texto.translate(str.maketrans("áéíóúü", "aeiouu"))


def normalizar(frase):
    f = frase.strip().lower()
    f = re.sub(r"^(?:r\d+\s*[:.)\-]|\d+\s*[.)])\s*", "", f)   # quita "R1:" o "1." del inicio
    f = re.sub(r"[.;!?¿¡]+", "", f)
    f = re.sub(r"\s+", " ", f)
    return f.strip(" ,")


# ---------------- Construcción y validación (no guardan nada) ----------------
def construir(texto):
    for op, patron in PATRONES:
        m = re.match(patron, texto)
        if m:
            return (op,) + tuple(construir(g.strip(" ,")) for g in m.groups())
    return ("txt", texto)


def _hojas_txt(arbol):
    if arbol[0] == "txt":
        return [arbol[1]]
    lista = []
    for h in arbol[1:]:
        lista += _hojas_txt(h)
    return lista


def _tiene_op(arbol, op):
    if arbol[0] == "txt":
        return False
    return arbol[0] == op or any(_tiene_op(h, op) for h in arbol[1:])


def validar(arbol, texto):
    if re.search(r"si y s[oó]lo si|\bsii\b", texto) and not _tiene_op(arbol, "iff"):
        raise ErrorFrase("el «si y solo si» está incompleto (faltan proposiciones a ambos lados).")
    for a in _hojas_txt(arbol):
        if not a:
            raise ErrorFrase("hay un operando vacío (falta texto junto a un conectivo).")
        if a == "no":
            raise ErrorFrase("la negación «no» no tiene a qué negar.")
        mal = [p for p in a.split() if p in SOBRANTES]
        if mal:
            raise ErrorFrase(
                f"la proposición «{a}» contiene el conectivo «{mal[0]}» mal formado "
                "(¿falta una parte de la frase?)."
            )


# ---------------- Tabla de átomos ----------------
class TablaAtomos:
    """Asigna una letra a cada proposición simple. Mismo texto = misma letra."""

    def __init__(self):
        self.claves = {}   # texto sin acentos -> letra
        self.items = []    # [(letra, significado)]

    def _letra_libre(self):
        usadas = {l for l, _ in self.items}
        for l in LETRAS:
            if l not in usadas:
                return l
        i = 1
        while f"p{i}" in usadas:
            i += 1
        return f"p{i}"

    def registrar(self, texto):
        clave = sin_acentos(texto)
        if clave not in self.claves:
            letra = self._letra_libre()
            self.claves[clave] = letra
            self.items.append((letra, texto))
        return self.claves[clave]

    def quitar(self, letra):
        self.items = [(l, t) for l, t in self.items if l != letra]
        self.claves = {k: l for k, l in self.claves.items() if l != letra}


def traducir(arbol, tabla):
    if arbol[0] == "txt":
        return ("var", tabla.registrar(arbol[1]))
    return (arbol[0],) + tuple(traducir(h, tabla) for h in arbol[1:])


# ---------------- Fórmulas ----------------
def es_literal(f):
    return f[0] == "var" or (f[0] == "not" and f[1][0] == "var")


def _par(f):
    return texto_formula(f) if f[0] in ("var", "not") else "(" + texto_formula(f) + ")"


def texto_formula(f):
    """Fórmula legible; paréntesis solo alrededor de subfórmulas binarias."""
    t = f[0]
    if t == "var":
        return f[1]
    if t == "not":
        return "¬" + _par(f[1])
    return f"{_par(f[1])} {SIMBOLOS[t]} {_par(f[2])}"


# ---------------- Base de conocimiento ----------------
class Linea:
    def __init__(self, numero, original, etiqueta, formula, error):
        self.numero = numero        # número de línea en el cuadro de texto (1, 2, ...)
        self.original = original
        self.etiqueta = etiqueta    # "R1", "R2"... (None si hubo error)
        self.formula = formula
        self.error = error

    @property
    def tipo(self):
        if self.formula is None:
            return "Error"
        return "Hecho" if es_literal(self.formula) else "Regla"


class Base:
    def __init__(self, lineas, atomos, reglas):
        self.lineas = lineas        # todas las líneas leídas (válidas e inválidas)
        self.atomos = atomos        # [(letra, significado)]
        self.reglas = reglas        # [("R1", formula), ...] solo las válidas

    @property
    def errores(self):
        return [l for l in self.lineas if l.error]

    @property
    def letras(self):
        return [a[0] for a in self.atomos]


def analizar_base(texto):
    """Lee varias reglas/hechos (una por línea). Una línea inválida no registra nada."""
    tabla = TablaAtomos()
    lineas, reglas = [], []
    for num, original in enumerate(texto.splitlines(), 1):
        if not original.strip() or original.strip().startswith("#"):
            continue
        norm = normalizar(original)
        if not norm:
            continue
        arbol = construir(norm)
        try:
            validar(arbol, norm)
        except ErrorFrase as e:
            lineas.append(Linea(num, original.strip(), None, None, str(e)))
            continue
        formula = traducir(arbol, tabla)
        etiqueta = f"R{len(reglas) + 1}"
        reglas.append((etiqueta, formula))
        lineas.append(Linea(num, original.strip(), etiqueta, formula, None))
    return Base(lineas, tabla.items, reglas)


# ---------------- Biblioteca persistente (variables y reglas guardadas) ----------------
def letras_de(f):
    if f[0] == "var":
        return [f[1]]
    lista = []
    for h in f[1:]:
        lista += letras_de(h)
    return lista


def _a_tupla(x):
    return tuple(_a_tupla(i) for i in x) if isinstance(x, list) else x


class ResultadoAgregar:
    def __init__(self):
        self.lineas = []        # todas las líneas leídas (válidas e inválidas)
        self.atomos = {}        # letra -> True si es NUEVA, False si YA EXISTÍA
        self.reglas = {}        # índice de regla -> True si es NUEVA, False si YA EXISTÍA

    @property
    def errores(self):
        return [l for l in self.lineas if l.error]


class Biblioteca:
    """Guarda las variables (átomos) y reglas entre una frase y otra.
    - Una línea inválida no guarda nada.
    - Una variable o regla que ya existe se reutiliza y se marca como YA EXISTÍA."""

    def __init__(self):
        self.tabla = TablaAtomos()
        self.reglas = []        # [{"formula": ..., "texto": "..."}]

    @property
    def atomos(self):
        return self.tabla.items

    @property
    def letras(self):
        return [l for l, _ in self.tabla.items]

    def reglas_para_tableau(self):
        return [(f"R{i + 1}", r["formula"]) for i, r in enumerate(self.reglas)]

    def vaciar(self):
        self.tabla = TablaAtomos()
        self.reglas = []

    def agregar(self, texto):
        res = ResultadoAgregar()
        for num, original in enumerate(texto.splitlines(), 1):
            if not original.strip() or original.strip().startswith("#"):
                continue
            norm = normalizar(original)
            if not norm:
                continue
            arbol = construir(norm)
            try:
                validar(arbol, norm)
            except ErrorFrase as e:
                res.lineas.append(Linea(num, original.strip(), None, None, str(e)))
                continue                      # frase inválida: no se guarda nada
            antes = set(self.letras)
            formula = traducir(arbol, self.tabla)
            for letra in letras_de(formula):
                res.atomos.setdefault(letra, letra not in antes)
            idx = next((i for i, r in enumerate(self.reglas) if r["formula"] == formula), None)
            nueva = idx is None
            if nueva:
                self.reglas.append({"formula": formula, "texto": original.strip()})
                idx = len(self.reglas) - 1
            res.reglas.setdefault(idx, nueva)
            res.lineas.append(Linea(num, original.strip(), f"R{idx + 1}", formula, None))
        return res

    def eliminar_regla(self, idx):
        """Quita la regla y las variables que ya no usa ninguna regla."""
        del self.reglas[idx]
        usadas = {l for r in self.reglas for l in letras_de(r["formula"])}
        for letra in self.letras:
            if letra not in usadas:
                self.tabla.quitar(letra)

    # ----- guardar / cargar en un archivo JSON -----
    def guardar(self, ruta):
        import json
        datos = {"atomos": [[l, t] for l, t in self.tabla.items],
                 "reglas": [{"formula": r["formula"], "texto": r["texto"]} for r in self.reglas]}
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)

    def cargar(self, ruta):
        import json
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        tabla = TablaAtomos()
        for letra, texto in datos["atomos"]:
            tabla.items.append((letra, texto))
            tabla.claves[sin_acentos(texto)] = letra
        reglas = [{"formula": _a_tupla(r["formula"]), "texto": r["texto"]} for r in datos["reglas"]]
        self.tabla, self.reglas = tabla, reglas
