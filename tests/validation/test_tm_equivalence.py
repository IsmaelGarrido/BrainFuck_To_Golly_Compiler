"""
test_tm_equivalence.py
----------------------
Verificación de EQUIVALENCIA de la Etapa 2 del compilador:

    AST  ──tm_encoder.encode(alphabet_size=2)──►  MTProgram

Metodología
-----------
Para cada programa BF de prueba:
  1. Se genera la MT con encode(ast, alphabet_size=2).
  2. Se SIMULA la MT paso a paso (función de transición aplicada hasta
     alcanzar el estado de aceptación), con un simulador independiente
     del encoder.
  3. Se ejecuta el mismo programa con un intérprete BF de referencia en
     semántica binaria (celda mod 2).
  4. Se comparan los estados finales de la cinta (celdas no nulas).
"""

import pytest
from collections import defaultdict
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                'bf2gol', 'compiler', 'codegen'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                'bf2gol', 'compiler', 'semantic'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                'bf2gol', 'compiler', 'lexical'))

from lexer import tokenize
from parser import parse, Instruction, Loop
from tm_encoder import encode

ALPHABET_SIZE = 2  # cinta binaria (límite de diseño del TFG)


# ── Simulador de la MT generada (independiente del encoder) ───────────────────

def simulate_tm(source: str,
                initial: dict[int, int] | None = None,
                max_steps: int = 200_000) -> dict[int, int]:
    """
    Simula la MT producida por encode(parse(tokenize(source)), alphabet_size=2).

    Aplica la función de transición (state, symbol) → (write, dir, new_state)
    hasta alcanzar el estado de aceptación.

    Parámetros:
        source:    código BF
        initial:   contenido inicial de la cinta {posición: bit} (entradas)
        max_steps: límite de pasos antes de declarar no-terminación

    Retorna:
        Estado final de la cinta como {posición: bit} (solo celdas no nulas).

    Lanza:
        TMDivergence: si la MT no halta en max_steps (bucle infinito real).
    """
    tm = encode(parse(tokenize(source)), alphabet_size=ALPHABET_SIZE)
    trans = {(t.state, t.read): t for t in tm.transitions}

    tape: dict[int, int] = defaultdict(int)
    if initial:
        for pos, val in initial.items():
            tape[pos] = val

    head, state, steps = 0, tm.initial_state, 0
    while state != tm.accept_state:
        if steps >= max_steps:
            raise TMDivergence(f"{source!r}: no haltó en {max_steps} pasos")
        key = (state, tape[head])
        if key not in trans:
            raise RuntimeError(
                f"{source!r}: sin transición en q{state} leyendo {tape[head]}"
            )
        t = trans[key]
        tape[head] = t.write
        if   t.direction == 'R': head += 1
        elif t.direction == 'L': head -= 1
        # 'N' = sin movimiento
        state = t.new_state
        steps += 1

    return {k: v for k, v in tape.items() if v != 0}


class TMDivergence(Exception):
    """La MT no halta (bucle infinito legítimo del programa)."""


# ── Intérprete BF de referencia en semántica binaria ──────────────────────────

def bf_binary(source: str,
              initial: dict[int, int] | None = None,
              tape_size: int = 256,
              max_steps: int = 200_000) -> dict[int, int]:
    """
    Ejecuta el programa BF con celdas binarias (mod 2) y cinta opcionalmente
    pre-inicializada. Sirve como ground truth independiente de la MT.

    Retorna el estado final de la cinta como {posición: bit}.
    """
    tape = [0] * tape_size
    if initial:
        for pos, val in initial.items():
            tape[pos] = val
    ptr = [0]
    steps = [0]

    ast = parse(tokenize(source))

    def run(nodes):
        for n in nodes:
            if isinstance(n, Instruction):
                op = n.op
                if   op == '+': tape[ptr[0]] = (tape[ptr[0]] + 1) % 2
                elif op == '-': tape[ptr[0]] = (tape[ptr[0]] - 1) % 2
                elif op == '>': ptr[0] += 1
                elif op == '<': ptr[0] -= 1
                # '.' y ',' fuera de alcance binario de equivalencia
            elif isinstance(n, Loop):
                while tape[ptr[0]] != 0:
                    steps[0] += 1
                    if steps[0] >= max_steps:
                        raise TMDivergence(f"{source!r}: intérprete no halta")
                    run(n.body)

    run(ast)
    return {i: v for i, v in enumerate(tape) if v != 0}


# ── Helper de aserción ────────────────────────────────────────────────────────

def assert_equivalent(source: str, initial: dict[int, int] | None = None):
    """La MT generada y el intérprete BF coinciden en el estado final."""
    mt_tape = simulate_tm(source, initial)
    bf_tape = bf_binary(source, initial)
    assert mt_tape == bf_tape, (
        f"Programa {source!r} (entrada {initial}):\n"
        f"  MT generada : {mt_tape}\n"
        f"  intérprete BF: {bf_tape}"
    )


# ── Categoría A: Operaciones básicas sobre un bit ─────────────────────────────

class TestBitBasico:
    """'+' y '-' como flip de bit (mod 2)."""

    @pytest.mark.parametrize("source", [
        '+',        # set
        '++',       # flip x2 = 0
        '+++',      # = 1
        '-',        # clear desde 0 = 1 (underflow mod 2)
        '+-',       # = 0
        '-+',       # = 0
    ])
    def test_flip(self, source):
        assert_equivalent(source)


# ── Categoría B: Movimiento de cabeza y multicelda ────────────────────────────

class TestMulticelda:
    """'>' y '<' mueven el cabezal; celdas independientes."""

    @pytest.mark.parametrize("source", [
        '>+',           # bit en celda 1
        '+>+',          # dos bits
        '+>+>+',        # tres bits
        '>>+',          # bit en celda 2
        '>+<',          # ida y vuelta
        '+>++>+',       # celda 1 vuelve a 0 (flip x2)
    ])
    def test_movimiento(self, source):
        assert_equivalent(source)


# ── Categoría C: Bucles simples ───────────────────────────────────────────────

class TestBuclesSimples:
    """[...] ejecuta el cuerpo mientras la celda actual sea 1."""

    @pytest.mark.parametrize("source", [
        '[-]',          # cinta vacía: no entra
        '+[-]',         # entra, vacía la celda, sale
        '+[->+<]',      # mueve el bit de celda 0 a celda 1
        '[->+<]',       # no entra (celda 0 = 0)
        '+[-]+[-]',     # dos bucles secuenciales
    ])
    def test_bucle(self, source):
        assert_equivalent(source)


# ── Categoría D: Bucles anidados que terminan ─────────────────────────────────

class TestAnidados:
    """Bucles anidados con terminación garantizada."""

    @pytest.mark.parametrize("source", [
        '+[-[-]]',          # clear celda 0; bucle interno no entra
        '+>+<[->[-]<]',     # estructura anidada que termina
        '+>+<[>[-]<[-]]',   # AND-like destructivo
    ])
    def test_anidado(self, source):
        assert_equivalent(source)


# ── Categoría E: Programas lógicos sobre tablas de verdad completas ──────────

class TestLogicaBinaria:
    """
    Programas que operan sobre dos bits de entrada (a, b) precargados
    en las celdas 0 y 1. Se verifica la equivalencia MT ≡ intérprete
    para las 4 combinaciones de entrada.

    No se comprueba que el programa implemente una tabla de verdad
    canónica concreta — eso es propiedad del programa, no del encoder.
    Lo que se verifica es que la MT computa EXACTAMENTE lo mismo que el
    programa BF para toda entrada.
    """

    PROGRAMAS = {
        'and_destructivo': '>[<[-]>-]<',
        'or_destructivo':  '>[<[-]+>-]<',
    }

    @pytest.mark.parametrize("nombre,source", list(PROGRAMAS.items()))
    @pytest.mark.parametrize("a", [0, 1])
    @pytest.mark.parametrize("b", [0, 1])
    def test_tabla_verdad(self, nombre, source, a, b):
        assert_equivalent(source, initial={0: a, 1: b})


# ── Categoría F: Acotación del número de estados ──────────────────────────────

class TestEstadosAcotados:
    """
    Confirma que el alfabeto binario mantiene el número de estados
    pequeño — premisa del alcance del TFG para que el wiring en GoL
    sea tratable.
    """

    @pytest.mark.parametrize("source,max_estados", [
        ('+',         5),
        ('+>+',       8),
        ('+[-]',     10),
        ('+[->+<]',  15),
        ('+[-[-]]',  20),
    ])
    def test_pocos_estados(self, source, max_estados):
        tm = encode(parse(tokenize(source)), alphabet_size=ALPHABET_SIZE)
        n = len(set(t.state for t in tm.transitions))
        assert n <= max_estados, f"{source!r}: {n} estados > {max_estados}"

    def test_alfabeto_binario(self):
        """La MT generada usa exclusivamente alfabeto {0, 1}."""
        tm = encode(parse(tokenize('+[->+<]')), alphabet_size=ALPHABET_SIZE)
        assert tm.tape_alphabet == {0, 1}


# ── Categoría G: Fidelidad ante divergencia ───────────────────────────────────

class TestDivergencia:
    """
    Si el programa BF diverge (bucle infinito legítimo), la MT generada
    también debe diverger. Esto es FIDELIDAD: la MT replica el
    comportamiento del programa, halte o no.
    """

    def test_bucle_infinito_diverge_en_ambos(self):
        # '+[>+[-]<]': el cuerpo del bucle externo nunca modifica celda[0],
        # que vale 1 → bucle infinito legítimo del programa.
        src = '+[>+[-]<]'
        with pytest.raises(TMDivergence):
            simulate_tm(src, max_steps=50_000)
        with pytest.raises(TMDivergence):
            bf_binary(src, max_steps=50_000)