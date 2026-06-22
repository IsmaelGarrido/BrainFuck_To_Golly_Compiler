"""
tests/test_compiler_driver.py
-----------------------------
Tests del controlador compiler_BF_to_GoL: orquestación de las cuatro etapas
del pipeline activo (lexer → parser → tm_encoder → turing rule) y aplicación
de las decisiones fijadas (A1, B, C1, E1, F).

Verifica que:
  * los programas válidos producen una turing rule con formato consumible por
    turing.py (las mismas comprobaciones que el parser de Simkin),
  * cada clase de error se detecta en la fase correcta,
  * el colapso de '.' y el dimensionado de cinta se aplican.
"""

import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_COMPILER = os.path.join(_HERE, "..")          # carpeta compiler/
for _sub in ("", "lexical", "semantic"):
    _p = os.path.join(_COMPILER, _sub) if _sub else _COMPILER
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from compiler_BF_to_GoL import compile_bf, compile_file, CompilerError


# ── Validador del formato de turing.py ───────────────────────────────────────

def _valida_formato_simkin(rule: str):
    """Replica las exigencias de parse_turing_rule de turing.py."""
    lines = rule.split("\n")
    assert len(lines) >= 3
    tape_line, head_line, *rule_lines = lines

    # Cinta y head_start son enteros.
    [int(x) for x in tape_line.split(" ")]
    int(head_line)

    reglas = [l for l in rule_lines if len(l.split(" ")) >= 5]
    estados, heads = set(), set()
    for l in reglas:
        campos = l.split(" ")
        assert len(campos) == 5
        int(campos[0]); int(campos[1]); int(campos[2]); int(campos[3])
        assert "l" in campos[4] or "r" in campos[4]
        estados.add(int(campos[0]))
        heads.add(int(campos[1]))

    # Tabla completa: turing.py aborta si faltan combinaciones.
    num_states = max(estados) + 1
    num_head = max(heads) + 1
    assert len(reglas) >= num_head * num_states


# ── Compilaciones válidas ────────────────────────────────────────────────────

@pytest.mark.parametrize("src", ["+", "-", ">+", "+>+", ">+>+<<",
                                 "+[>+<-]", "+[->+<]", ">>>+"])
def test_compila_y_formato_valido(src):
    """Programas válidos compilan y producen formato consumible por turing.py."""
    rule = compile_bf(src)
    _valida_formato_simkin(rule)


def test_head_start_en_origen_por_defecto():
    """El cabezal arranca en el origen (head_start 0)."""
    rule = compile_bf(">+")
    assert rule.split("\n")[1] == "0"


# ── Decisión F: programa vacío ───────────────────────────────────────────────

@pytest.mark.parametrize("src", ["", "   ", "hola mundo", "# comentario",
                                 ".", "...", " . . . "])
def test_programa_vacio_es_error(src):
    """Un programa sin instrucciones efectivas (incl. solo '.' o comentarios)
    es error en fase 'vacío' (decisión F, comprobada tras colapsar '.')."""
    with pytest.raises(CompilerError) as exc:
        compile_bf(src)
    assert exc.value.phase == "vacío"


# ── Decisión A1: cruce de origen ─────────────────────────────────────────────

@pytest.mark.parametrize("src", ["<", "<+", ">+<<", "[<]", "+[<]"])
def test_cruce_origen_es_error(src):
    """Mover el puntero a la izquierda del origen es error en fase 'cinta'."""
    with pytest.raises(CompilerError) as exc:
        compile_bf(src)
    assert exc.value.phase == "cinta"


def test_deriva_derecha_no_es_error():
    """Un bucle con deriva a la derecha es seguro en cinta unilateral."""
    rule = compile_bf("[>]")          # no lanza
    _valida_formato_simkin(rule)


# ── Errores de sintaxis y codificación ───────────────────────────────────────

@pytest.mark.parametrize("src", ["[", "]", "+[", "][", "[[]"])
def test_corchetes_desequilibrados(src):
    """Corchetes desequilibrados → fase 'sintáctico'."""
    with pytest.raises(CompilerError) as exc:
        compile_bf(src)
    assert exc.value.phase == "sintáctico"


@pytest.mark.parametrize("src", [",", "+,", ">,<"])
def test_input_no_soportado(src):
    """',' (input) no está soportado → fase 'codificación'."""
    with pytest.raises(CompilerError) as exc:
        compile_bf(src)
    assert exc.value.phase == "codificación"


# ── Decisión B: colapso de '.' ───────────────────────────────────────────────

def test_punto_colapsa():
    """'+.+' produce la misma regla que '++' ('.' no llega a la MT)."""
    assert compile_bf("+.+") == compile_bf("++")


def test_punto_en_bucle_colapsa():
    """'.' se elimina también dentro de bucles."""
    assert compile_bf("+[.>+<.-]") == compile_bf("+[>+<-]")


# ── Decisión C1: dimensionado de cinta ───────────────────────────────────────

@pytest.mark.parametrize("src,min_celdas", [
    ("+", 2), (">+", 3), (">>>+", 5),
])
def test_cinta_dimensionada(src, min_celdas):
    """La cinta por defecto cubre el alcance del programa, inicializada a 0."""
    rule = compile_bf(src)
    cinta = rule.split("\n")[0].split(" ")
    assert len(cinta) >= min_celdas
    assert all(c == "0" for c in cinta)


def test_cinta_personalizada():
    """Se puede pasar una cinta inicial explícita."""
    rule = compile_bf("+", input_tape=[1, 0, 1])
    assert rule.split("\n")[0] == "1 0 1"


# ── compile_file ─────────────────────────────────────────────────────────────

def test_compile_file(tmp_path):
    """compile_file lee un .bf y compila."""
    p = tmp_path / "prog.bf"
    p.write_text("+>+")
    rule = compile_file(str(p))
    _valida_formato_simkin(rule)


def test_compile_file_inexistente():
    """Un fichero inexistente → fase 'entrada'."""
    with pytest.raises(CompilerError) as exc:
        compile_file("/no/existe/prog.bf")
    assert exc.value.phase == "entrada"


# ── Equivalencia: el driver coincide con compile_to_simkin directo ───────────

@pytest.mark.parametrize("src", ["+", ">+", "+[>+<-]"])
def test_driver_coincide_con_compile_to_simkin(src):
    """El driver produce la misma regla que compile_to_simkin para programas
    sin '.' (mismo pipeline, sin sorpresas)."""
    from tm_encoder import compile_to_simkin
    assert compile_bf(src) == compile_to_simkin(src, alphabet_size=2)
