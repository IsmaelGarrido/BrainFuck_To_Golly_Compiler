"""
BrainFuck_To_Golly_Compiler/compiler/source/interpreter.py
----------------------------------------------------
Brainfuck reference Interpreter.

Executes a Branfuck AST and returns the final state of the tape and an exit produced by '.'.

NOT part of compilation pipeline, but a validation tool to compare results of GoL simulation
and BF program execution.
"""

from dataclasses import dataclass, field
from parser import Instruction, Loop, AST

@dataclass
class InterpreterResult:
    """
    Result of executing a BF program.
    
    Atributes:
        tape:       final state of tape(List of Integer 0-255)
        output:     ASCII values produced by '.'
        pointer:    final position of pointer
    """
    tape:       list[int]
    output:     list[int]
    pointer:    int


    def output_as_str(self) -> str:
        """Transforms output to ASCII string."""
        return ''.join(chr(v) for v in self.output)
    
    def tape_nonzero(self) -> dict[int, int]:
        """Returns only the non-zero positions of the tape."""
        return {i: v for i, v in enumerate(self.tape) if v != 0}
    
class InterpreterError(Exception):
    """Interpreter Runtime Error"""
    pass

class InputNotSupportedError(InterpreterError):
    """
    Instruction ',' not supported by v1 of compiler.
    
    The test programs don't need an input, can be implemented in future extensions.
    """
    pass

class TapeUnderflowError(InterpreterError):
    """Pointer tried to move left from position 0."""
    pass

def interpret(ast: AST, 
              tape_size: int = 30000, 
              max_steps: int = 10000000) -> InterpreterResult:
    """
    Executes a BF AST and returns the output.
    
    Parameters:
        ast:        AST produce by parser
        tape_size:  initial tape size (expanded if necesary)
        max_steps:  steps limit to detect infinite loops
    Returns:
        InterpeterResult:   contains final state of tape, output of '.'
        and final pointer position
    Raises:
        InputNotSupportedError: if program uses ','
        TapeUnderflowError:     if pointer goes to the left of 0
        InterpreterError:       if max_steps is surpased (infinite loop)
    """
    tape    = [0] * tape_size
    ptr     = 0
    output  = []
    steps   = [0]

    def run(nodes: list) -> None:
        for node in nodes:
            steps[0] += 1
            if steps[0] > max_steps:
                raise InterpreterError(
                    f"Limit of {max_steps:,} steps surpased."
                    f"Program main contain infinite loop."
                )
            
            if isinstance(node, Instruction):
                nonlocal ptr
                match node.op:
                        case '>':
                            ptr += 1

                            if ptr >= len(tape):
                                tape.extend([0] * tape_size)
                        
                        case '<':
                            if ptr == 0:
                                raise TapeUnderflowError(
                                    "Pointer tried moving left from tape position 0"
                                )
                            ptr -= 1
                        
                        case '+':
                            tape[ptr] = (tape[ptr] + 1) % 256

                        case ''