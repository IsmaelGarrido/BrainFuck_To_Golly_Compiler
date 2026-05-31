"""
BrainFuck_To_Golly_Compiler/compiler/lexical/lexer.py
----------------------------------------------------
Lexic Analysis.

Read source code written on Brainfuck and return
a valid token list, discarding comments and the like.
"""

# Valid Token List
VALID_TOKENS = frozenset('><+-.,[]')

class LexerError(Exception):
    """Lexic Error"""
    pass

def tokenize(source: str) -> list[str]:
    if not isinstance(source, str):
        raise LexerError(f"Expected string, recived {type(source).__name__}")
    
    tokens = [ch for ch in source if ch in VALID_TOKENS]
    return tokens

def tokenize_file(path: str) -> list[str]:
    with open(path, 'r', encoding='utf-8') as f:
        source = f.read()
    return tokenize(source)