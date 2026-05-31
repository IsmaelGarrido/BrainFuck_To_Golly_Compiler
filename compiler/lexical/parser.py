"""
BrainFuck_To_Golly_Compiler/compiler/lexical/parser.py
----------------------------------------------------
Syntactic Analysis

Transforms token list produced by lexer into AST
(Abstract Syntactic Tree) according to BF Grammar

Grammar:
    program     => instruction*
    instruction => simple | loop
    simple      => '+'|'-'|'>'|'<'|'.'|','
    loop        => '[' instruction* ']'

Possible errors:
    - '[' without ']' -> ParseError
    - ']' without '[']
""" 

from dataclasses import dataclass, field

@dataclass
class Instruction:
    """
    Leaf AST Node - Simple instruction
    
    Atributes:
        op: one of 6 simple tokens: + - > < . ,
    """
    op: str
    def __repr__(self):
        return f"Instruction('{self.op}')"
    
@dataclass
class Loop:
    """
    Complex AST Node -  Loop
    
    Atributes:
        body: list of instructions (Instruction | Loop) inside the loop (can be empty)
    """
    body: list = field(default_factory=list)

    def __repr__(self):
            return f"Loop({self.body})"
    

AST = list[Instruction | Loop]

class ParseError(Exception):
    """
     Syntax Error - brackets not closed
     
     Atributes:
        message: error description
        position: index of error token
    """
    def __init__(self, message:str, position: int = -1):
        super().__init__(message)
        self.position = position
    
def parse(tokens: list[str]) -> AST:
    """
     Tranforms a BF token list into an AST.
     
     Implements LL(1) parser base on stack. Each stack level
     represents the current nest context
        - Lvl 0 : root context (main program)
        - Lvl n : inside n nested loops

    Parameters:
        tokens: valid BF token list (lexer output)

    Returns:
        AST: List of Instruction and Loop nodes at root level

    Launches:
        ParseError: if brackets are not closed
    """
    stack: list[list] = [[]]

    for i, token in enumerate(tokens):
        if token == '[':
                 stack.append([])

        elif token == ']':
            if len(stack) < 2:
                raise ParseError(
                    f"']' in position {i} doesn't have matching '['",
                    position = i
                )
            body = stack.pop()
            stack[-1].append(Loop(body=body))

        else:
            stack[-1].append(Instruction(op=token))
        
    if len(stack) != 1:
         unclosed = len(stack) -1
         raise ParseError(
            f"{unclosed} loop(s) '[' without matching ']'"
         )
    
    return stack[0]
    
def depth(ast:AST) -> int:
    """
    Calculates the max depth of nesting loops
    
    Example:
        depth([Instruction('+')]) == 0
        depth([Loop([Instruction('-')])]) == 1
        depth([Loop([Loop([Instruction('-')])])]) == 2
    """
    max_depth = 0
    for node in ast:
        if isinstance(node, Loop):
                max_depth = max(max_depth, 1 + depth(node.body))
    return max_depth
    
def count_instructions(ast:AST) -> dict[str, int]:
    """
    Counts occurencies of each instruction on the whole AST,
    including nested loops.
    
    Returns:
        Dictionary {token: count} for each of the 8 possible tokens
    """
    counts = {op: 0 for op in '><+-.,[]'}
    for node in ast:
        if isinstance(node, Instruction):
            counts[node.op] += 1
        elif isinstance(node, Loop):
             counts['['] += 1
             counts[']'] += 1
             inner = count_instructions(node.body)
             for op, n in inner.items():
                  counts[op] += n
    return counts