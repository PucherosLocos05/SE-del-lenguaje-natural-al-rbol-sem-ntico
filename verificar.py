"""Verificación automática del programa. Ejecuta:  python verificar.py

Compara el programa contra respuestas conocidas y contra un método independiente
(probar todas las combinaciones de V/F). No necesita ventana ni tkinter.
"""
import itertools
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parser_nl import Biblioteca, analizar_base, texto_formula, letras_de
from tableau import Tableau, ArbolDemasiadoGrande, literal, formatear_asignacion

resultados = []
RUTA_TEMPORAL = os.path.join(tempfile.gettempdir(), "_verificar_biblioteca.json")


def chequear(nombre, ok, detalle=""):
    resultados.append(ok)
    print(f"  {'✓' if ok else '✗ FALLA'}  {nombre}" + (f"   → {detalle}" if (detalle and not ok) else ""))


def seccion(titulo):
    print(f"\n{titulo}")


def evaluar(f, a):
    t = f[0]
    if t == "var":
        return a[f[1]]
    if t == "not":
        return not evaluar(f[1], a)
    x, y = evaluar(f[1], a), evaluar(f[2], a)
    return {"and": x and y, "or": x or y, "imp": (not x) or y, "iff": x == y}[t]


# ============================================================
seccion("1. TRADUCCIÓN DEL ESPAÑOL A FÓRMULAS (el parser)")
casos = [
    ("Si voy a trabajar entonces gano dinero", "p → q"),
    ("Llueve y hace frío", "p ∧ q"),
    ("Voy al cine o me quedo en casa", "p ∨ q"),
    ("No llueve", "¬p"),
    ("Comeré si y solo si la comida está buena", "p ↔ q"),
    ("Es de día", "p"),
    ("No es cierto que llueva y haga frío", "¬(p ∧ q)"),
    ("Si llueve y hace frío entonces me quedo en casa", "(p ∧ q) → r"),
    ("Si no llueve entonces voy al parque", "¬p → q"),
    ("Si hay sol o hace calor entonces voy a la alberca", "(p ∨ q) → r"),
    ("Apruebo sii estudio", "p ↔ q"),
    ("La lámpara no funciona", "¬p"),
    ("El caballero no usa la espada o la princesa huye", "¬p ∨ q"),
    ("Si la princesa no se salva entonces el dragón gana", "¬p → q"),
    ("Llueve y no hace frío", "p ∧ ¬q"),
    ("No es de día", "¬p"),
]
for frase, esperado in casos:
    b = Biblioteca()
    r = b.agregar(frase)
    obtenido = texto_formula(r.lineas[0].formula) if r.lineas and r.lineas[0].formula else "(error)"
    chequear(f"«{frase}»  =  {esperado}", obtenido == esperado, f"obtuvo {obtenido}")

seccion("2. ÁTOMOS: misma idea = misma letra, y la negación no crea átomos nuevos")
b = Biblioteca()
b.agregar("Si voy a trabajar entonces gano dinero\nNo voy a trabajar\nVoy a trabajar o estudio")
chequear("«voy a trabajar» en tres reglas es siempre la misma letra (p)",
         [l for l, t in b.atomos].count("p") == 1 and b.atomos[0][1] == "voy a trabajar")
chequear("«No voy a trabajar» se guarda como ¬p, no como átomo nuevo",
         texto_formula(b.reglas[1]["formula"]) == "¬p" and len(b.atomos) == 3,
         f"átomos: {b.atomos}")
b = Biblioteca()
b.agregar("Comeré si y solo si la comida está buena\nSi comere entonces estoy feliz")
chequear("«Comeré» y «comere» (con y sin acento) son el mismo átomo", len(b.atomos) == 3, f"{b.atomos}")

b = Biblioteca()
b.agregar("Si hay luz, entonces la lámpara funciona.\nHay luz.\nLa lámpara no funciona..")
chequear("«La lámpara no funciona» es ¬(la lámpara funciona): no crea un átomo nuevo (caso de la captura)",
         len(b.atomos) == 2 and texto_formula(b.reglas[2]["formula"]) == "¬q", f"{b.atomos}")
b = Biblioteca()
b.agregar("El dragón duerme\nEl dragón no duerme")
chequear("«duerme» y «no duerme» comparten la misma letra", len(b.atomos) == 1, f"{b.atomos}")

seccion("3. FRASES NO VÁLIDAS (no deben guardar nada)")
for mala in ["Si llueve", "llueve y", "no", "si y solo si", "Si llueve entonces", "Hola mundo y"]:
    b = Biblioteca()
    b.agregar("Llueve y hace frío")
    antes = (list(b.atomos), len(b.reglas))
    r = b.agregar(mala)
    chequear(f"«{mala}» se rechaza y no guarda variables ni reglas",
             bool(r.errores) and (list(b.atomos), len(b.reglas)) == antes)

seccion("4. BIBLIOTECA (guardar, reutilizar y detectar repetidos)")
b = Biblioteca()
r1 = b.agregar("Si llueve entonces me quedo en casa")
chequear("primera frase: 2 variables NUEVAS y 1 regla NUEVA",
         list(r1.atomos.values()) == [True, True] and list(r1.reglas.values()) == [True])
r2 = b.agregar("Si llueve y hace frío entonces me quedo en casa")
chequear("segunda frase reutiliza «llueve» y «me quedo en casa» (YA EXISTÍAN) y solo «hace frío» es nueva",
         sorted(r2.atomos.values()) == [False, False, True])
r3 = b.agregar("Si llueve entonces me quedo en casa")
chequear("repetir una frase completa no duplica la regla (YA EXISTÍA)",
         list(r3.reglas.values()) == [False] and len(b.reglas) == 2)
b.guardar(RUTA_TEMPORAL)
c = Biblioteca()
c.cargar(RUTA_TEMPORAL)
chequear("guardar y cargar en JSON deja la misma biblioteca", c.atomos == b.atomos and c.reglas == b.reglas)
b.eliminar_regla(1)
chequear("al eliminar una regla se borran las variables que ya nadie usa",
         [t for _, t in b.atomos] == ["llueve", "me quedo en casa"], f"{b.atomos}")

seccion("5. TABLEAU: respuestas conocidas")
def correr(texto):
    base = analizar_base(texto)
    return base, Tableau(base.reglas)

base, t = correr("Si hay dragón entonces el caballero usa la espada\n"
                 "Si el caballero usa la espada entonces la princesa se salva\nHay dragón")
asigs = [formatear_asignacion(t.asignacion(h), base.letras) for h in t.ramas_abiertas()]
chequear("dragón → espada → princesa, con dragón: única solución p=V, q=V, r=V",
         asigs == ["p = V, q = V, r = V"], f"{asigs}")

base, t = correr("Si hay dragón entonces el caballero usa la espada\n"
                 "Si el caballero usa la espada entonces la princesa se salva\nHay dragón\n"
                 "No es cierto que la princesa se salva")
chequear("agregar «la princesa NO se salva» vuelve inconsistente la base (todas las ramas se cierran)",
         not t.satisfacible and not t.ramas_abiertas())

base, t = correr("Si llueve entonces me mojo\nLlueve\nNo me mojo")
chequear("modus ponens contradicho: p→q, p, ¬q se cierra", not t.satisfacible)

base, t = correr("Si hay luz, entonces la lámpara funciona.\nHay luz.\nLa lámpara no funciona..")
chequear("caso de la captura (luz → lámpara, hay luz, la lámpara no funciona): INSATISFACIBLE",
         not t.satisfacible and len(base.atomos) == 2)

base, t = correr("Llueve y no llueve")
chequear("una contradicción sola (p ∧ ¬p) cierra todas sus ramas", not t.satisfacible)

base, t = correr("Llueve o no llueve")
chequear("una tautología (p ∨ ¬p) no cierra ninguna rama", len(t.ramas_abiertas()) == 2)

base, t = correr("Apruebo si y solo si estudio\nEstudio")
asigs = [formatear_asignacion(t.asignacion(h), base.letras) for h in t.ramas_abiertas()]
chequear("p↔q con q verdadera: apruebo debe ser V", asigs == ["p = V, q = V"], f"{asigs}")

# ============================================================
seccion("6. TABLEAU vs MÉTODO INDEPENDIENTE (todas las combinaciones V/F)")
random.seed(2024)
LETRAS = list("pqrs")


def aleatoria(d):
    if d == 0 or random.random() < 0.25:
        return ("var", random.choice(LETRAS))
    t = random.choice(["not", "and", "or", "imp", "iff"])
    if t == "not":
        return ("not", aleatoria(d - 1))
    return (t, aleatoria(d - 1), aleatoria(d - 1))


probadas = fallas = omitidas = estructura_mal = 0
for _ in range(2000):
    reglas = [(f"R{k + 1}", aleatoria(3)) for k in range(random.randint(1, 4))]
    try:
        t = Tableau(reglas)
    except ArbolDemasiadoGrande:
        omitidas += 1
        continue
    probadas += 1
    verdad = {v for v in itertools.product([True, False], repeat=4)
              if all(evaluar(f, dict(zip(LETRAS, v))) for _, f in reglas)}
    del_arbol = set()
    for h in t.ramas_abiertas():
        asig = t.asignacion(h)
        libres = [l for l in LETRAS if l not in asig]
        for comb in itertools.product([True, False], repeat=len(libres)):
            a = dict(asig)
            a.update(zip(libres, comb))
            del_arbol.add(tuple(a[l] for l in LETRAS))
    if del_arbol != verdad or t.satisfacible != bool(verdad):
        fallas += 1
    # estructura: ramas abiertas solo con literales/aplicadas y sin letra+negación; cerradas con contradicción real
    ok_est = True
    for h in t.hojas():
        ruta = t.camino(h)
        if h.cerrada:
            letra, a, b_ = h.contradiccion
            ok_est &= t.nodos[a - 1].formula == ("var", letra) and t.nodos[b_ - 1].formula == ("not", ("var", letra))
        else:
            vistos = set()
            for n in ruta:
                lit = literal(n.formula)
                if lit is None:
                    ok_est &= n.aplicada is not None
                else:
                    ok_est &= (lit[0], not lit[1]) not in vistos
                    vistos.add(lit)
    estructura_mal += (not ok_est)
chequear(f"{probadas} bases aleatorias: las ramas abiertas coinciden EXACTO con las combinaciones que hacen verdaderas todas las reglas",
         fallas == 0, f"{fallas} discrepancias")
chequear("estructura del árbol: ramas abiertas solo con letras (o fórmulas ya aplicadas) y sin letra+negación; ramas cerradas con contradicción real",
         estructura_mal == 0, f"{estructura_mal} árboles mal formados")
print(f"        (se omitieron {omitidas} bases por ser árboles de más de 1500 nodos)")

seccion("7. TABLAS DE VERDAD DE LOS CONECTIVOS (si existe sistema_logica.py)")
try:
    from sistema_logica import OPERACIONES
    esperado = {
        "¬": {(True,): False, (False,): True},
        "∧": {(True, True): True, (True, False): False, (False, True): False, (False, False): False},
        "∨": {(True, True): True, (True, False): True, (False, True): True, (False, False): False},
        "⇒": {(True, True): True, (True, False): False, (False, True): True, (False, False): True},
        "⇔": {(True, True): True, (True, False): False, (False, True): False, (False, False): True},
    }
    for op, tabla in esperado.items():
        chequear(f"tabla de verdad de {op}", all(OPERACIONES[op](*k) == v for k, v in tabla.items()))
except ImportError:
    print("  (se omite: no está sistema_logica.py en la carpeta)")

try:
    os.remove(RUTA_TEMPORAL)
except OSError:
    pass

# ============================================================
total, buenas = len(resultados), sum(resultados)
print("\n" + "=" * 60)
print(f"RESULTADO: {buenas} de {total} comprobaciones correctas")
print("TODO BIEN ✓" if buenas == total else "HAY FALLAS ✗ (revisa las líneas marcadas)")
sys.exit(0 if buenas == total else 1)
