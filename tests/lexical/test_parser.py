"""
Brainfuck_To_Golly_Compiler/tests/lexical/test_parser.py
-----------------------------------------------
Unit Test for parser module
"""

import sys, os

import pytest 
from compiler.lexical.lexer import tokenize, tokenize_file, LexerError, VALID_TOKENS
from compiler.lexical.parser import parse, Instruction, Loop, ParseError, depth, count_instructions

def I(op): return Instruction(op)
def L(*body): return Loop(list(body))

def test_empty_program():
    """Empty List produces Empty AST."""
    assert parse([]) == []

def test_simple_instruction():
    """A single token produces a single instruction."""
    assert parse(tokenize("+")) == [I('+')]

def test_all_simple_tokens():
    """The 6 simple tokens are parsed correctly"""
    expected = [I('+'), I('-'), I('>'), I('<'), I('.'), I(',')]
    assert parse(tokenize("+-><.,")) == expected

def test_simple_sequence():
    """A simple instruction sequence produces a plain list."""
    assert parse(tokenize("+++")) == [I('+'), I('+'), I('+')]

def test_empty_loop():
    """An empty loop produces a Loop with empty body."""
    assert parse(tokenize("[]")) == [L()]

def test_simple_loop():
    """Loop with simple instructions."""
    assert parse(tokenize("[-]")) == [L(I('-'))]

def test_multiple_token_loop():
    """Loop with multiple instructions."""
    assert parse(tokenize("[->+<]")) == [L(I('-'), I('>'), I('+'), I('<'))]

def test_instructions_before_loop():
    """Simple instructions before loop"""
    assert parse(tokenize("++[-]")) == [I('+'), I('+'), L(I('-'))]

def test_instructions_after_loop():
    """Simple instructions after loop"""
    assert parse(tokenize("[-]++")) == [L(I('-')), I('+'), I('+')]

def test_add_program():
    """Full Program: 2+3 -> ++>+++<[->+<]"""
    assert parse(tokenize('++>+++<[->+<]')) == [
        I('+'), I('+'), I('>'), I('+'), I('+'), I('+'), I('<'), L(I('-'), I('>'), I('+'), I('<')) 
    ]

def test_set_zero_program():
    """Full Program: [-]"""
    assert parse(tokenize("[-]")) == [L(I('-'))]

def test_program_regressive_count():
    """Full program: +++++[-]"""
    assert parse(tokenize("+++++[-]")) == [
        I('+'), I('+'), I('+'), I('+'), I('+'), L(I('-'))
    ]

def test_simple_nested_loop():
    """Loop inside loop - 1 level of nesting"""
    assert parse(tokenize("[+][-]")) == [L(I('+')), L(I('-'))]

def test_deep_nested_loop():
    """Three levels of nesting"""
    assert parse(tokenize('[[[+]]]')) == [L(L(L(I('+'))))]

def test_multiple_simple_loops():
    """Two consecutive loops with same level of nesting."""
    assert parse(tokenize('[+][-]')) == [L(I('+')), L(I('-'))]

def test_loop_with_instructions_and_subloop():
    """Loop with simple instructions and a subloop."""
    assert parse(tokenize('+[-[>]+]')) == [
        I('+'), L(I('-'), L(I('>')), I('+'))
    ]

def test_comments_inside_loop():
    """Coments intertwinned inside a loop are ignored"""
    assert parse(tokenize('[comment - comment]')) == [L(I('-'))]

def test_error_close_without_open():
    """']' sin '[' raises ParseError."""
    with pytest.raises(ParseError):
        parse([']'])

def test_error_close_without_open_with_instructions():
    """']' without '[' after instructions raises ParseError."""
    with pytest.raises(ParseError):
        parse(['+', '+', ']'])

def test_error_open_without_close():
    """'[' without ']' raises ParseError."""
    with pytest.raises(ParseError):
        parse(['['])

def test_error_open_without_close_with_instructions():
    """'[' before instructions without ']' raises ParseError."""
    with pytest.raises(ParseError):
        parse(['[', '+', '+'])
    
def test_error_incorrect_nesting_close():
    """Extra ']' raises ParseError."""
    with pytest.raises(ParseError):
        parse(['[', ']', ']'])

def test_error_incorrect_nesting_open():
    """Extra '[' raises ParseError."""
    with pytest.raises(ParseError):
        parse(['[', '[', ']'])

def test_parse_error_includes_position():
    """ParseError includes problem token's position"""
    with pytest.raises(ParseError) as exc_info:
        parse(['+', ']'])
    assert exc_info.value.position == 1

def test_depth_plain_program():
    """Loop-less program with depth 0."""
    assert depth(parse(tokenize('+->'))) == 0

def test_depth_one_loop():
    """Loop with depth 1."""
    assert depth(parse(tokenize('[-]'))) == 1

def test_depth_two_loop():
    """Loop with depth 2."""
    assert depth(parse(tokenize('[[-]]'))) == 2
    
def test_depth_three_loop():
    """Loop with depth 3."""
    assert depth(parse(tokenize('[[[-]]]'))) == 3

def test_depth_parallel_loops():
    """Two loops with same depth."""
    assert depth(parse(tokenize('[+][-]'))) == 1

def test_count_simple_instructions():
    """Correctly counts simple instructions."""
    counts = count_instructions(parse(tokenize('++->')))
    assert counts['+'] == 2
    assert counts['-'] == 1
    assert counts['>'] == 1
    assert counts['<'] == 0

def test_count_instructions_with_loop():
    """Counts instructions inside loops."""
    counts = count_instructions(parse(tokenize('[++-]')))
    assert counts['+'] == 2
    assert counts['-'] == 1
    assert counts['['] == 1
    assert counts[']'] == 1

def test_count_nested_instructions():
    """Counts instructions inside nested loops."""
    counts = count_instructions(parse(tokenize('[+[-]]')))
    assert counts['+'] == 1
    assert counts['-'] == 1
    assert counts['['] == 2
    assert counts[']'] == 2    