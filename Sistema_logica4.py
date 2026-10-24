import itertools
import re

# ---------------- Biblioteca (persiste mientras el programa está abierto) ----------------
X = []  # átomos:  X[1], X[2], ...
R = []  # reglas:  R[1], R[2], ...  -> (op1, op2, conectivo) o (op1, ¬)

# El orden importa: del conectivo de menor precedencia al de mayor.
PATRONES = [
    ("⇔", r"^(.+?),? (?:si y s[oó]lo si|sii|cuando y s[oó]lo cuando|es equivalente a|equivale a) (.+)$"),
    ("⇒", r"^si (.+?),? entonces (.+)$"),
    ("⇒", r"^(.+?) implica (.+)$"),
    ("¬", r"^(?:no es cierto que|es falso que) (.+)$"),   # negación de alcance amplio
    ("∨", r"^o bien (.+?),? o (.+)$"),
    ("∨", r"^(.+?) o (.+)$"),
    ("∧", r"^tanto (.+?) como (.+)$"),
    ("∧", r"^(.+?) (?:y|pero|además) (.+)$"),
    ("¬", r"^no (.+)$"),                                    # negación simple
]

NOMBRES = {"⇔": "Doble implicación (bicondicional)", "⇒": "Implicación", "∨": "Disyunción", "∧": "Conjunción", "¬": "Negación"}

# Palabras de conectivos que NO deben quedar dentro de un átomo (señal de frase mal formada)
SOBRANTES = {"si", "entonces", "implica", "y", "o", "pero", "además", "tanto"}


class FraseInvalida(Exception):
    pass


# ---------------- Paso 1: construir el árbol (NO toca la biblioteca) ----------------
def normalizar(frase):
    frase = frase.strip().lower()
    frase = re.sub(r"[.;!?¿¡]+", "", frase)
    return re.sub(r"\s+", " ", frase)


def construir(texto):
    for op, patron in PATRONES:
        m = re.match(patron, texto)
        if m:
            hijos = [construir(g.strip(" ,")) for g in m.groups()]
            return (op, hijos)
    return ("atomo", texto)


def ops_del_arbol(arbol):
    if arbol[0] == "atomo":
        return []
    ops = [arbol[0]]
    for h in arbol[1]:
        ops += ops_del_arbol(h)
    return ops


def atomos_del_arbol(arbol):
    if arbol[0] == "atomo":
        return [arbol[1]]
    lista = []
    for h in arbol[1]:
        lista += atomos_del_arbol(h)
    return lista


# ---------------- Paso 2: validar ----------------
def validar(arbol):
    for a in atomos_del_arbol(arbol):
        if not a:
            raise FraseInvalida("hay un operando vacío (falta texto junto a un conectivo).")
        palabras = a.split()
        if a == "no":
            raise FraseInvalida("la negación 'no' no tiene a qué negar.")
        if re.search(r"si y s[oó]lo si|\bsii\b", a):
            raise FraseInvalida(
                f"'{a}' tiene un 'si y solo si' incompleto (faltan proposiciones a ambos lados)."
            )
        mal = [p for p in palabras if p in SOBRANTES]
        if mal:
            raise FraseInvalida(
                f"la proposición '{a}' contiene el conectivo '{mal[0]}' mal formado "
                "(¿falta una parte de la frase?)."
            )
    if arbol[0] == "atomo":
        raise FraseInvalida("no se detectó ningún conectivo (∧, ∨, ⇒, ¬) en la frase.")


# ---------------- Paso 3: registrar en la biblioteca (solo si es válida) ----------------
def registrar(arbol, info):
    """Guarda en X y R lo que falte. Devuelve la referencia ('X[i]' o 'R[i]')."""
    if arbol[0] == "atomo":
        texto = arbol[1]
        nueva = texto not in X
        if nueva:
            X.append(texto)
        ref = f"X[{X.index(texto) + 1}]"
        info["atomos"].setdefault(ref, nueva)
        return ref

    op, hijos = arbol
    refs = tuple(registrar(h, info) for h in hijos)
    regla = refs + (op,)
    nueva = regla not in R
    if nueva:
        R.append(regla)
    ref = f"R[{R.index(regla) + 1}]"
    info["reglas"].setdefault(ref, nueva)
    return ref


def formula(ref):
    i = int(ref[2:-1]) - 1
    if ref.startswith("X"):
        return X[i]
    regla = R[i]
    if len(regla) == 2:
        return f"¬({formula(regla[0])})"
    return f"({formula(regla[0])} {regla[2]} {formula(regla[1])})"


# ---------------- Tablas de verdad ----------------
OPERACIONES = {
    "¬": lambda p: not p,
    "∧": lambda p, q: p and q,
    "∨": lambda p, q: p or q,
    "⇒": lambda p, q: (not p) or q,
    "⇔": lambda p, q: p == q,
}

MAX_VARIABLES = 14  # 2**14 = 16384 filas como máximo


def _num(ref):
    return int(ref[2:-1])


def dependencias(ref):
    """Devuelve (átomos, reglas) que intervienen en `ref`.
    Los átomos van ordenados por índice; las reglas de adentro hacia afuera."""
    atomos, reglas = set(), []

    def visitar(r):
        if r.startswith("X"):
            atomos.add(r)
            return
        if r in reglas:
            return
        for operando in R[_num(r) - 1][:-1]:
            visitar(operando)
        reglas.append(r)

    visitar(ref)
    return sorted(atomos, key=_num), reglas


def evaluar(ref, asignacion):
    """Valor (True/False) de un átomo o regla dada una asignación {'X[1]': True, ...}."""
    if ref.startswith("X"):
        return asignacion[ref]
    regla = R[_num(ref) - 1]
    valores = [evaluar(o, asignacion) for o in regla[:-1]]
    return OPERACIONES[regla[-1]](*valores)


def tabla_verdad(ref):
    """Tabla de verdad completa de `ref`.
    Devuelve (átomos, reglas, filas) con filas = [(valores_átomos, valores_reglas), ...]."""
    atomos, reglas = dependencias(ref)
    if len(atomos) > MAX_VARIABLES:
        raise ValueError(f"Demasiadas variables ({len(atomos)}); el máximo es {MAX_VARIABLES}.")
    filas = []
    for combo in itertools.product([True, False], repeat=len(atomos)):
        asignacion = dict(zip(atomos, combo))
        filas.append((combo, tuple(evaluar(r, asignacion) for r in reglas)))
    return atomos, reglas, filas


def clasificar(filas):
    """Tautología, contradicción o contingencia según la última columna (la regla principal)."""
    finales = [f[1][-1] for f in filas]
    if all(finales):
        return "Tautología (siempre verdadera)"
    if not any(finales):
        return "Contradicción (siempre falsa)"
    return "Contingencia (a veces verdadera, a veces falsa)"


def tabla_conectivo(op):
    """Tabla de verdad básica de un conectivo: (encabezados, filas)."""
    if op == "¬":
        return ["P", "¬P"], [(p, OPERACIONES[op](p)) for p in (True, False)]
    filas = [(p, q, OPERACIONES[op](p, q)) for p in (True, False) for q in (True, False)]
    return ["P", "Q", f"P {op} Q"], filas


def vf(valor):
    return "V" if valor else "F"


def texto_tabla(ref):
    """Tabla de verdad de `ref` lista para imprimir en consola."""
    atomos, reglas, filas = tabla_verdad(ref)
    columnas = atomos + reglas
    lineas = ["Leyenda:"]
    for a in atomos:
        lineas.append(f"  {a} = {X[_num(a) - 1]}")
    for r in reglas:
        lineas.append(f"  {r} = {formula(r)}")
    anchos = [max(len(c), 1) for c in columnas]
    lineas.append("")
    lineas.append(" | ".join(c.center(w) for c, w in zip(columnas, anchos)))
    lineas.append("-+-".join("-" * w for w in anchos))
    for valores_a, valores_r in filas:
        celdas = [vf(v) for v in valores_a + valores_r]
        lineas.append(" | ".join(c.center(w) for c, w in zip(celdas, anchos)))
    lineas.append("")
    lineas.append(f"Resultado: {clasificar(filas)}")
    return "\n".join(lineas)


def texto_conectivos():
    """Tablas de verdad básicas de los cinco conectivos, para consola."""
    bloques = []
    for op in ("¬", "∧", "∨", "⇒", "⇔"):
        encabezados, filas = tabla_conectivo(op)
        lineas = [f"{NOMBRES[op]} ({op})", "  " + " | ".join(h.center(7) for h in encabezados)]
        for fila in filas:
            lineas.append("  " + " | ".join(vf(v).center(7) for v in fila))
        bloques.append("\n".join(lineas))
    return "\n\n".join(bloques)


# ---------------- Interfaz ----------------
def analizar_frase(frase):
    """Valida y guarda la frase en la biblioteca.
    Lanza FraseInvalida (sin guardar nada) o devuelve un diccionario con el resultado."""
    texto = normalizar(frase)
    arbol = construir(texto)
    if re.search(r"si y s[oó]lo si|\bsii\b", texto) and arbol[0] != "⇔" \
            and not any(op == "⇔" for op in ops_del_arbol(arbol)):
        raise FraseInvalida("el 'si y solo si' está incompleto (faltan proposiciones a ambos lados).")
    validar(arbol)

    info = {"atomos": {}, "reglas": {}}
    raiz = registrar(arbol, info)

    principal = R[int(raiz[2:-1]) - 1][-1]
    usadas = []
    for ref in info["reglas"]:
        op = R[int(ref[2:-1]) - 1][-1]
        if op not in usadas:
            usadas.append(op)
    return {"raiz": raiz, "principal": principal, "usadas": usadas, "info": info}


def procesar(frase):
    try:
        res = analizar_frase(frase)
    except FraseInvalida as e:
        print(f"\n✗ Frase NO válida: {e}")
        print("  No se guardó ninguna variable ni regla.\n")
        return
    raiz, principal, usadas, info = res["raiz"], res["principal"], res["usadas"], res["info"]


    print("\n" + "=" * 64)
    print(f"Lógica principal: {NOMBRES[principal]} ({principal})")
    print("Conectivos detectados: " + ", ".join(f"{NOMBRES[o]} ({o})" for o in usadas))
    print(f"Fórmula: {formula(raiz)}")

    print("\nVariables de esta frase:")
    for ref, nueva in info["atomos"].items():
        estado = "NUEVA, guardada" if nueva else "YA EXISTÍA en la biblioteca"
        print(f"  {ref} = {X[int(ref[2:-1]) - 1]}   [{estado}]")

    print("\nReglas de esta frase:")
    for ref, nueva in info["reglas"].items():
        regla = R[int(ref[2:-1]) - 1]
        estado = "NUEVA, guardada" if nueva else "YA EXISTÍA en la biblioteca"
        print(f"  {ref} = ({', '.join(regla)})   [{estado}]")

    nv = sum(info["atomos"].values())
    nr = sum(info["reglas"].values())
    print(f"\nResumen: {nv} variable(s) nueva(s), {len(info['atomos']) - nv} repetida(s); "
          f"{nr} regla(s) nueva(s), {len(info['reglas']) - nr} repetida(s).")
    print("=" * 64 + "\n")
    return raiz


def ver_biblioteca():
    print("\n--- BIBLIOTECA ---")
    print("Variables:")
    for i, a in enumerate(X, 1):
        print(f"  X[{i}] = {a}")
    if not X:
        print("  (vacía)")
    print("Reglas:")
    for i, r in enumerate(R, 1):
        print(f"  R[{i}] = ({', '.join(r)})")
    if not R:
        print("  (vacía)")
    print()


def main():
    print("SISTEMA DE LÓGICA EN LENGUAJE NATURAL")
    print("Escribe una frase. Comandos: 'tabla' (tabla de verdad de la última frase), "
          "'conectivos' (tablas básicas),\n'ver' (biblioteca), 'limpiar' (vaciarla), 'salir'.\n")
    ultima = None
    while True:
        frase = input("Frase: ").strip()
        cmd = frase.lower()
        if cmd in ("salir", "q", "exit"):
            break
        elif cmd == "ver":
            ver_biblioteca()
        elif cmd == "conectivos":
            print("\n" + texto_conectivos() + "\n")
        elif cmd == "tabla":
            if ultima is None:
                print("Primero escribe una frase válida.\n")
            else:
                try:
                    print("\n" + texto_tabla(ultima) + "\n")
                except ValueError as e:
                    print(f"\n{e}\n")
        elif cmd == "limpiar":
            X.clear()
            R.clear()
            ultima = None
            print("Biblioteca vaciada.\n")
        elif frase:
            raiz = procesar(frase)
            if raiz:
                ultima = raiz


if __name__ == "__main__":
    main()
