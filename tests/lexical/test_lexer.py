"""
Brainfuck_To_Golly_Compiler/tests/lexical/test_lexer.py
-----------------------------------------------
Unit Test for lexer module
"""

import pytest
from compiler.lexical.lexer import tokenize, tokenize_file, LexerError, VALID_TOKENS

def test_simple_tokens():
    """Tokens are recognized correctly."""
    assert tokenize("><+-.,[]") == ['>', '<', '+', '-', '.', ',' , '[', ']']

def test_empty_imput():
    """Empty string returns empty list."""
    assert tokenize('') == []

def test_only_comment():
    """Text without valid tokens returns empty list."""
    assert tokenize('This is a coment') == []
    assert tokenize(' \n\t ') == []

def test_comment_discard():
    """Inbetween comments are discarded."""
    assert tokenize('++ this is a comment') == ['+','+']

def test_linebreak_ignored():
    """Line breaks are comments and thus ignored."""
    assert tokenize ("++\n>\n+++") == ['+', '+', '>', '+', '+', '+']

def test_add_program():
    """Tokenizing a simple addition: 2+3."""
    assert tokenize ("++>+++<[->+<]") == ['+', '+', '>', '+', '+', '+', '<', '[', '-', '>', '+', '<', ']']

def test_add_program_with_comments():
    """Inline comments inside a program are discarded"""
    assert tokenize ("add two ++ move right > add three +++ move left < loop [->+<]") == ['+', '+', '>', '+', '+', '+', '<', '[', '-', '>', '+', '<', ']']

def test_error_detection():
    """Imputing something that isn't a String returns LexerError."""
    with pytest.raises(LexerError):
        tokenize(123)
    with pytest.raises(LexerError):
        tokenize(None)

def test_valid_tokens_recognized():
    """All characters in VALID_TOKENS are recognized individually."""
    for token in VALID_TOKENS:
        assert tokenize(token) == [token], f"Token '{token}' not recognized."

def test_special_characters_ignored():
    """Special characters and Unicode ignored without issue."""
    assert tokenize("+ ñ € ~ +") == ['+', '+']

def test_hello_world():
    """Hello World test program tokenizes without issue."""
    program = (
        "++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]"
        ">>.>---.+++++++..+++.>>.<-.<.+++.------.--------.>>+.>++."
    )

    tokens = tokenize(program)
    assert all(token in VALID_TOKENS for token in tokens)
    assert len(tokens) == len(program)

def test_tokenize_file(tmp_path):
    """tokenize_file reads a .bf file completely."""
    file = tmp_path/'test.bf'
    file.write_text('++ add >\n+++\n')
    tokens = tokenize_file(str(file))
    assert tokens == ['+', '+', '>', '+', '+', '+']

    