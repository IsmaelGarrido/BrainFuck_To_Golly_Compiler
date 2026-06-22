"""
tests/test_simkin_export.py
---------------------------
Verifica la conexión de la fase 2 del compilador con el simulador de MT de
Michael Simkin:

  1. eliminate_stationary: elimina los movimientos 'N' PRESERVANDO la
     semántica (la MT transformada computa lo mismo que el intérprete BF de
     referencia), incluyendo programas con bucles.

  2. to_simkin_rule / compile_to_simkin: producen el formato exacto que el
     script turing.py de Simkin exige (tabla completa estado×símbolo, solo
     l/r, líneas de 5 campos, cinta y head_start en las dos primeras líneas).

  3. End-to-end: BF → MT sin N → archivo Simkin, re-parseado con la misma
     lógica que turing.py, preserva la semántica frente al intérprete BF.
"""

import sys, os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lexical"))

import pytest
from tm_encoder import (
    encode_source, eliminate_stationary, to_simkin_rule, compile_to_simkin,
)
from lexer import tokenize
from parser import parse

def simulate_program(program, initial=None, max_steps=200_000):
    """Simula cualquier MTProgram aplicando su función de transición."""
    trans = {(t.state, t.read): t for t in program.transitions}
    tape = defaultdict(int)
    if initial:
        for pos, val in initial.items():
            tape[pos] = val
    head, state, steps = 0, program.initial_state, 0
    while state != program.accept_state:
        if steps >= max_steps:
            raise RuntimeError(f"no haltó en {max_steps}")
        key = (state, tape[head])
        if key not in trans:
            raise RuntimeError(f"sin transición en q{state} leyendo {tape[head]}")
        t = trans[key]
        tape[head] = t.write
        if   t.direction == 'R': head += 1
        elif t.direction == 'L': head -= 1
        state = t.new_state
        steps += 1
    return {k: v for k, v in tape.items() if v != 0}


def bf_binary(source, initial=None, tape_size=256, max_steps=200_000):
    """Intérprete BF binario de referencia (ground truth)."""
    tape = [0] * tape_size
    if initial:
        for pos, val in initial.items():
            tape[pos] = val
    ptr = [0]
    steps = [0]
    ast = parse(tokenize(source))

    def run(nodes):
        for n in nodes:
            if hasattr(n, 'op'):
                op = n.op
                if   op == '+': tape[ptr[0]] = (tape[ptr[0]] + 1) % 2
                elif op == '-': tape[ptr[0]] = (tape[ptr[0]] - 1) % 2
                elif op == '>': ptr[0] += 1
                elif op == '<': ptr[0] -= 1
            else:
                while tape[ptr[0]] != 0:
                    steps[0] += 1
                    if steps[0] >= max_steps:
                        raise RuntimeError("no halta")
                    run(n.body)

    run(ast)
    return {i: v for i, v in enumerate(tape) if v != 0}


def simkin_parse_and_simulate(rule_str, max_steps=200_000):
    """
    Replica el parser de turing.py de Simkin y simula la semántica lógica
    resultante, para comprobar que nuestro archivo se interpreta como
    pretendemos (sin ejecutar Golly).
    """
    lines = rule_str.split("\n")
    init_tape_syms = [int(x) for x in lines[0].split(" ")]
    rule_lines = [l for l in lines[2:] if len(l.split(" ")) == 5]

    trans = {}
    for l in rule_lines:
        tape, head, new_tape, new_head, rl = l.split(" ")
        trans[(int(head), int(tape))] = (
            int(new_tape), int(new_head), 'R' if 'r' in rl else 'L'
        )

    tape = defaultdict(int)
    for i, s in enumerate(init_tape_syms):
        tape[i] = s
    pos, state, steps = 0, 0, 0
    while steps < max_steps:
        key = (state, tape[pos])
        if key not in trans:
            break
        nt, ns, d = trans[key]
        tape[pos] = nt
        pos += 1 if d == 'R' else -1
        state = ns
        steps += 1
    return {k: v for k, v in tape.items() if v != 0}


def simkin_head_range(rule_str, settle=2000, window=40):
    """
    Corre la MT estilo Simkin y devuelve el rango (max-min) de posiciones del
    cabezal en los últimos 'window' pasos tras 'settle' pasos.
    """
    lines = rule_str.split("\n")
    init = [int(x) for x in lines[0].split(" ")]
    rule_lines = [l for l in lines[2:] if len(l.split(" ")) == 5]
    trans = {}
    for l in rule_lines:
        tp, hd, nt, nh, d = l.split(" ")
        trans[(int(hd), int(tp))] = (int(nt), int(nh), 'R' if 'r' in d else 'L')
    tape = defaultdict(int)
    for i, s in enumerate(init):
        tape[i] = s
    pos, state, steps = 0, 0, 0
    posiciones = []
    while steps < settle + window:
        key = (state, tape[pos])
        if key not in trans:
            break
        nt, ns, d = trans[key]
        tape[pos] = nt
        pos += 1 if d == 'R' else -1
        state = ns
        steps += 1
        if steps > settle:
            posiciones.append(pos)
    if not posiciones:
        return 0
    return max(posiciones) - min(posiciones)

PROGRAMAS = [
    "+", "++", "+++", "-", ">", "<", ">+", "+>+", "><", ">>+<<",
    ">+>+<<", "+[>]", "+[-]", "+++[>+<-]", "+[->+<]",
]
@pytest.mark.parametrize("src", PROGRAMAS)
def test_eliminate_stationary_no_N(src):
    """Tras eliminate_stationary no queda ningún movimiento 'N'."""
    mt = eliminate_stationary(encode_source(src, alphabet_size=2))
    assert all(t.direction != 'N' for t in mt.transitions)


@pytest.mark.parametrize("src", PROGRAMAS)
def test_eliminate_stationary_preserva_semantica(src):
    """La MT sin 'N' computa lo mismo que el intérprete BF de referencia."""
    mt = eliminate_stationary(encode_source(src, alphabet_size=2))
    assert simulate_program(mt) == bf_binary(src)


def test_eliminate_stationary_idempotente_en_semantica():
    """Aplicarla dos veces no cambia el resultado computado."""
    mt1 = eliminate_stationary(encode_source("+>+", alphabet_size=2))
    mt2 = eliminate_stationary(mt1)
    assert simulate_program(mt1) == simulate_program(mt2)


def test_simkin_rule_estructura():
    """
    Cinta, head_start y una línea por combinación estado×símbolo.
    """
    mt = eliminate_stationary(encode_source("+", alphabet_size=2))
    rule = to_simkin_rule(mt)
    lines = rule.split("\n")
    rule_lines = lines[2:]
    assert len(rule_lines) == (mt.num_states + 1) * mt.alphabet_size


def test_simkin_rule_lineas_validas():
    """Cada línea de regla tiene 5 campos y dirección en {l, r}."""
    rule = compile_to_simkin("+>+", alphabet_size=2)
    for l in rule.split("\n")[2:]:
        campos = l.split(" ")
        assert len(campos) == 5
        assert campos[4] in ("l", "r")


def test_simkin_rule_sin_N():
    """El export nunca contiene movimientos 'N'."""
    rule = compile_to_simkin("+++[>+<-]", alphabet_size=2)
    for l in rule.split("\n")[2:]:
        assert l.split(" ")[4] in ("l", "r")


def test_simkin_rule_rechaza_N_sin_eliminar():
    """to_simkin_rule exige que ya no haya 'N'."""
    mt = encode_source("+", alphabet_size=2)   # tiene 'N'
    with pytest.raises(ValueError):
        to_simkin_rule(mt)


def test_simkin_rule_exige_estado_inicial_0():
    """Simkin requiere start state 0; nuestro encoder ya cumple."""
    mt = eliminate_stationary(encode_source("+", alphabet_size=2))
    assert mt.initial_state == 0
    # No lanza:
    to_simkin_rule(mt)


def test_simkin_tape_y_head_start():
    """La cinta y el head_start aparecen en las dos primeras líneas."""
    rule = compile_to_simkin("+", alphabet_size=2,
                             input_tape=[1, 0, 1], head_start=2)
    lines = rule.split("\n")
    assert lines[0] == "1 0 1"
    assert lines[1] == "2"


def test_simkin_tape_larga_no_rompe():
    """Una cinta de >=5 celdas no se confunde con reglas (Simkin extrae
    cinta/head antes del sort)."""
    rule = compile_to_simkin("+", alphabet_size=2,
                             input_tape=[1, 0, 1, 1, 0, 1], head_start=0)
    out = simkin_parse_and_simulate(rule)
    # '+' sobre cinta[0]=1 → 1+1=0; el resto intacto.
    assert out == {2: 1, 3: 1, 5: 1}

@pytest.mark.parametrize("src", ["+", "++", "+++", ">+", "+>+", ">+>+<<"])
def test_end_to_end_simkin_preserva_bf(src):
    """BF → archivo Simkin → parseo estilo Simkin == intérprete BF."""
    rule = compile_to_simkin(src, alphabet_size=2)
    assert simkin_parse_and_simulate(rule) == bf_binary(src)

@pytest.mark.parametrize("src", ["+", "++", ">+", "+>+", ">+>+<<", "+++[>+<-]"])
def test_halt_mantiene_cabezal_acotado(src):
    """
    El estado de parada es un oscilador de dos estados: el cabezal debe
    quedar acotado (rango pequeño), no marchar a la derecha por la cinta
    finita. Sin esto, un self-loop con 'r' empujaría el cabezal fuera de la
    cinta unilateral de Simkin.
    """
    rule = compile_to_simkin(src, alphabet_size=2)
    rango = simkin_head_range(rule, settle=2000, window=40)
    assert rango <= 2, f"el cabezal no está acotado (rango {rango})"


@pytest.mark.parametrize("src", ["+", "+++", ">+", "+>+", ">+>+<<", "+++[>+<-]"])
def test_halt_no_corrompe_cinta(src):
    """
    Tras muchos pasos de oscilación en el estado de parada, la cinta no debe
    corromperse: el resultado a 100 pasos y a 5000 pasos coincide y es
    correcto frente al intérprete BF.
    """
    rule = compile_to_simkin(src, alphabet_size=2)
    out_corto = simkin_parse_and_simulate(rule, max_steps=100)
    out_largo = simkin_parse_and_simulate(rule, max_steps=5000)
    assert out_corto == out_largo, "la cinta se corrompe con el tiempo"
    assert out_largo == bf_binary(src), "resultado distinto del intérprete BF"

def test_punto_colapsa_en_simkin():
    """'+.+' produce la misma turing rule que '++' (el '.' no llega a la MT)."""
    assert compile_to_simkin("+.+", alphabet_size=2) == \
           compile_to_simkin("++", alphabet_size=2)


def test_punto_colapsa_en_bucles():
    """El '.' se elimina también dentro de bucles."""
    assert compile_to_simkin("+[.>+<.-]", alphabet_size=2) == \
           compile_to_simkin("+[>+<-]", alphabet_size=2)


def test_strip_output_no_afecta_encode_source():
    """encode_source (compartido) sigue marcando is_output para el otro
    pipeline; el colapso es exclusivo del camino de Simkin."""
    mt = encode_source(".", alphabet_size=2)
    assert any(t.is_output for t in mt.transitions)


def test_strip_output_recursivo():
    """strip_output_nodes elimina todos los '.' a cualquier profundidad."""
    from tm_encoder import strip_output_nodes
    from parser import Instruction, Loop

    def count_dots(nodes):
        c = 0
        for n in nodes:
            if isinstance(n, Instruction) and n.op == '.':
                c += 1
            elif isinstance(n, Loop):
                c += count_dots(n.body)
        return c

    ast = parse(tokenize("+[.>.[.]]"))
    assert count_dots(strip_output_nodes(ast)) == 0


def test_solo_puntos_colapsa_a_vacio():
    """Un programa de solo '.' queda como AST vacío tras el colapso (lo que
    el driver tratará como programa vacío)."""
    from tm_encoder import strip_output_nodes
    assert strip_output_nodes(parse(tokenize("..."))) == []

@pytest.mark.parametrize("src", ["<", "<+", ">+<<", "[<]", "+[<]", "><<"])
def test_a1_rechaza_cruce_origen(src):
    """Mover el puntero a la izquierda del origen es error."""
    from tm_encoder import UnilateralTapeError
    with pytest.raises(UnilateralTapeError):
        compile_to_simkin(src, alphabet_size=2)


@pytest.mark.parametrize("src", ["+", ">+", ">+<", "[>]", "+[>]", "+[>+<-]",
                                 ">+>+<<", ">>>+<<<"])
def test_a1_acepta_seguros(src):
    """Programas que no cruzan el origen compilan (incluida deriva a la
    derecha, segura en cinta unilateral)."""
    rule = compile_to_simkin(src, alphabet_size=2)
    assert rule.split("\n")[1] == "0"        # head_start en el origen


def test_a1_deriva_derecha_no_se_rechaza():
    """Un bucle con deriva neta a la derecha NO se rechaza (es seguro)."""
    # No lanza:
    compile_to_simkin("[>]", alphabet_size=2)


def test_analyze_pointer_distingue_direcciones():
    """analyze_pointer separa cruce de origen (izq) de deriva derecha."""
    from tm_encoder import analyze_pointer
    izq = analyze_pointer("<+")
    der = analyze_pointer("[>]")
    assert izq["crosses_origin"] is True
    assert der["crosses_origin"] is False
    assert der["right_decidable"] is False
    assert der["origin_decidable"] is True

@pytest.mark.parametrize("src,min_len", [
    ("+", 2), (">+", 3), (">>>+", 5), (">+>+>+<<<", 5),
])
def test_c1_longitud_cinta(src, min_len):
    """La cinta por defecto cubre la posición máxima a la derecha + margen."""
    rule = compile_to_simkin(src, alphabet_size=2)
    cinta = rule.split("\n")[0].split(" ")
    assert len(cinta) >= min_len
    assert all(c == "0" for c in cinta)    


def test_c1_required_tape_length():
    """required_tape_length = max_right + 1 + margen."""
    from tm_encoder import required_tape_length
    assert required_tape_length(">>>+", margin=0) == 4 
    assert required_tape_length(">>>+", margin=1) == 5

def test_e1_rechaza_alfabeto_no_binario():
    """compile_to_simkin exige alphabet_size == 2."""
    with pytest.raises(ValueError):
        compile_to_simkin("+", alphabet_size=4)
    with pytest.raises(ValueError):
        compile_to_simkin("+", alphabet_size=256)


def test_e1_acepta_binario():
    """alphabet_size == 2 es válido."""
    compile_to_simkin("+", alphabet_size=2)   # no lanza
