"""
compiler/compiler_BF_to_GoL.py
------------------------------
Controlador del compilador BF → Game of Life (vía Simkin).

Orquesta las cuatro etapas del pipeline activo y valida entre ellas, abortando
con un mensaje claro si el programa Brainfuck no es compilable. El resultado es
una "turing rule" lista para el script turing.py de Michael Simkin, que
construye la máquina de Turing en el Juego de la Vida dentro de Golly.

Pipeline:
    BF source → [lexer] → [parser] → [tm_encoder] → turing rule (Simkin)
                                                  → turing.py (Golly) → GoL


Uso programático:
    from compiler_BF_to_GoL import compile_bf
    rule = compile_bf("+>+")          # devuelve la turing rule (str)

Uso por línea de comandos:
    python compiler_BF_to_GoL.py programa.bf            # imprime la regla
    python compiler_BF_to_GoL.py programa.bf -o out.txt # la escribe a fichero
    python compiler_BF_to_GoL.py -c "+>+"               # compila código inline
"""

import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
for _sub in ("lexical", "semantic", "codegen"):
    _path = os.path.join(_HERE, _sub)
    if _path not in sys.path:
        sys.path.insert(0, _path)

from lexer import tokenize, LexerError
from parser import parse, ParseError
from tm_encoder import (
    encode, eliminate_stationary, to_simkin_rule,
    strip_output_nodes, analyze_pointer, check_unilateral_safe,
    required_tape_length, EncoderError, UnilateralTapeError,
)

SIMKIN_ALPHABET = 2


class CompilerError(Exception):
    """
    Error de compilación reportable al usuario. Envuelve los errores de cada
    etapa (léxico, sintáctico, codificación, cinta unilateral, programa vacío)
    con un mensaje uniforme indicando en qué fase ocurrió.
    """
    def __init__(self, phase: str, message: str):
        self.phase = phase
        super().__init__(f"[{phase}] {message}")


def _effective_ast(source: str):
    """
    Ejecuta lexer + parser + colapso de '.' y devuelve el AST efectivo.

    Aplica la decisión B (colapsar '.') aquí, de modo que el chequeo de
    "programa vacío" (decisión F) se haga sobre el AST que realmente se va a
    codificar — recuérdese que '...' o un texto sin instrucciones son
    programas vacíos efectivos.

    Lanza CompilerError con la fase correspondiente si el léxico o la sintaxis
    fallan.
    """
    try:
        tokens = tokenize(source)
    except LexerError as e:
        raise CompilerError("léxico", str(e))

    try:
        ast = parse(tokens)
    except ParseError as e:
        raise CompilerError("sintáctico", str(e))

    return strip_output_nodes(ast)


def compile_bf(source: str,
               input_tape: list = None,
               head_start: int = 0) -> str:
    """
    Compila código Brainfuck a una turing rule de Simkin.

    Orquesta todo el pipeline y aplica las validaciones de las decisiones
    fijadas. Devuelve la cadena lista para pegar en turing.py.

    Parámetros:
        source:     código fuente Brainfuck.
        input_tape: cinta inicial (lista de 0/1). Si None, se dimensiona al
                    alcance del programa con ceros.
        head_start: posición inicial del cabezal (0 = origen, por defecto).

    Devuelve:
        La turing rule (str) en el formato de Simkin.
    """
    # Etapas 1-2 + colapso de '.'.
    ast = _effective_ast(source)

    # Decisión F: un programa sin instrucciones efectivas no genera MT.
    if not ast:
        raise CompilerError(
            "vacío",
            "el programa no contiene instrucciones efectivas; no hay máquina "
            "de Turing que generar. (Comentarios y '.' no cuentan como "
            "instrucciones para el export a Simkin.)"
        )

    try:
        check_unilateral_safe(source)
    except UnilateralTapeError as e:
        raise CompilerError("cinta", str(e))

    if input_tape is None:
        input_tape = [0] * required_tape_length(source)

    try:
        mt = encode(ast, alphabet_size=SIMKIN_ALPHABET)
        mt = eliminate_stationary(mt)
        rule = to_simkin_rule(mt, input_tape=input_tape, head_start=head_start)
    except EncoderError as e:
        raise CompilerError("codificación", str(e))

    return rule


def compile_file(path: str, **kwargs) -> str:
    """
    Compila un fichero .bf a una turing rule de Simkin.

    Parámetros:
        path:    ruta al fichero fuente Brainfuck.
        kwargs:  se pasan a compile_bf (input_tape, head_start).

    Lanza:
        CompilerError: fase 'entrada' si el fichero no se puede leer, o
        cualquier error de compilación de compile_bf.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        raise CompilerError("entrada", f"no se puede leer '{path}': {e}")
    return compile_bf(source, **kwargs)


def _main(argv=None):
    """Punto de entrada de línea de comandos."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="compiler_BF_to_GoL",
        description="Compila Brainfuck a una turing rule para el simulador "
                    "turing.py de Simkin (máquina de Turing en GoL).",
    )
    src_group = parser.add_mutually_exclusive_group(required=True)
    src_group.add_argument("file", nargs="?", help="fichero .bf de entrada")
    src_group.add_argument("-c", "--code", help="código Brainfuck inline")
    parser.add_argument("-o", "--output",
                        help="fichero de salida (por defecto: stdout)")
    parser.add_argument("--head-start", type=int, default=0,
                        help="posición inicial del cabezal (defecto 0)")
    args = parser.parse_args(argv)

    try:
        if args.code is not None:
            rule = compile_bf(args.code, head_start=args.head_start)
        else:
            rule = compile_file(args.file, head_start=args.head_start)
    except CompilerError as e:
        print(f"Error de compilación {e}", file=sys.stderr)
        return 1

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(rule)
        print(f"Turing rule escrita en {args.output}", file=sys.stderr)
    else:
        print(rule)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
