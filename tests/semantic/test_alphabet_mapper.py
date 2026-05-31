"""
Brainfuck_To_Golly_Compiler/tests/semantic/test_alphabet_mapper.py
-----------------------------------------------
Unit Test for alphabet mapper module.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'compiler', 'source'))

import pytest
from compiler.semantic.alphabet_mapper import(
    symbol_to_bits, bits_to_symbol, map_to_binary, map_source,
    MapperError, BITS_PER_SYMBOL, BINARY_ALPHABET
)
from compiler.semantic.tm_encoder import encode_source, TMProgram as TMProgram

def binary_tm(source: str) -> TMProgram:
    return map_source(source)

def test_symbol_to_bits_zero():
    assert symbol_to_bits(0) == (0,0,0,0,0,0,0,0)

def binary_tm(source: str) -> TMProgram:
    return map_source(source)

def test_symbol_to_bits_zero():
    assert symbol_to_bits(0) == (0,0,0,0,0,0,0,0)

def test_symbol_to_bits_one():
    assert symbol_to_bits(1) == (0,0,0,0,0,0,0,1)

def test_symbol_to_bits_255():
    assert symbol_to_bits(255) == (1,1,1,1,1,1,1,1)

def test_symbol_to_bits_128():
    assert symbol_to_bits(128) == (1,0,0,0,0,0,0,0)

def test_symbol_to_bits_length():
    for s in (0, 1, 127, 128, 255):
        assert len(symbol_to_bits(s)) == BITS_PER_SYMBOL

def test_symbol_to_bits_msb_first():
    bits = symbol_to_bits(128)
    assert bits[0] == 1
    assert all(b == 0 for b in bits[1:])

def test_symbol_to_bits_out_of_range():
    with pytest.raises(ValueError):
        symbol_to_bits(256)
    with pytest.raises(ValueError):
        symbol_to_bits(-1)

def test_bits_to_symbol_zero():
    assert bits_to_symbol((0,0,0,0,0,0,0,0)) == 0

def test_bits_to_symbol_one():
    assert bits_to_symbol((0,0,0,0,0,0,0,1)) == 1

def test_bits_to_symbol_255():
    assert bits_to_symbol((1,1,1,1,1,1,1,1)) == 255

def test_bits_to_symbol_wrong_lenght():
    with pytest.raises(ValueError):
        bits_to_symbol((0, 1, 0))

def test_bits_to_symbol_wrong_value():
    with pytest.raises(ValueError):
        bits_to_symbol((0,2,0))

def test_round_trip_all_symbols():
    for s in range(256):
        assert bits_to_symbol(symbol_to_bits(s)) == s

def test_binary_alphabet_size():
    assert binary_tm('+').alphabet_size == 2

def test_binary_symbols_only():
    tm = binary_tm('++>[-]')
    for t in tm.transitions:
        assert t.read in (0, 1)
        assert t.write in (0, 1)

def test_binary_tape_alphabet():
    assert binary_tm('+').tape_alphabet == {0, 1}

def test_binary_directions_valid():
    tm = binary_tm('><+-.')
    for t in tm.transitions:
        assert t.direction in ('L', 'R', 'N')

def test_binary_is_deterministic():
    for src in ('+', '-', '>', '<', '.', '[-]', '++>+++<[->+<]'):
        tm = binary_tm(src)
        assert tm.is_deterministic(), f"Non-deterministic for {src!r}"

def test_binary_more_states_than_original():
    for src in ('+', '++', '[-]', '><'):
        orig = encode_source(src)
        binary = map_to_binary(orig)
        assert binary.num_states > orig.num_states

def test_binary_initial_state_in_Q():
    tm = binary_tm('+')
    assert tm.initial_state in tm.Q

def test_binary_accept_state_in_Q():
    tm = binary_tm('+')
    assert tm.initial_state in tm.Q

def test_binary_accept_state_in_Q():
    tm = binary_tm('+')
    assert tm.accept_state in tm.Q

def test_binary_Q_size_matches_num_states():
    for src in ('+', '[-]', '++>+++<[->+<]'):
        tm = binary_tm(src)
        assert len(tm.Q) == tm.num_states

def test_bits_per_symbol_is_eight():
    assert BITS_PER_SYMBOL == 8

def test_more_transition_tan_original():
    orig = encode_source('+')
    binary = map_to_binary(orig)
    assert len(binary.transitions) > len(orig.transitions)

def test_output_flag_preserver():
    tm = binary_tm('.')
    assert any(t.is_output for t in tm.transitions)

def test_mapper_error_wrong_alphabet_size():
    import dataclasses
    orig = encode_source('+')
    corrupt = dataclasses.replace(orig, alphabet_size = 10)
    with pytest.raises(MapperError):
        map_to_binary(corrupt)

def test_read_phase_preserves_bit():
    """During READ phase the bit under the head is not modified."""
    tm = binary_tm('+')
    t = tm.transition_for(tm.initial_state, 0)
    assert t is not None
    assert t.read == t.write

def test_simple_program_non_empty():
    for src in ('+', '-', '>', '<', '.', '[-]'):
        assert len(binary_tm(src).transitions) > 0

def test_map_source_matches_manual():
    manual = map_to_binary(encode_source('+'))
    shorthand = map_source('+')
    assert len(manual.transitions) == len(shorthand.transitions)
    assert manual.alphabet_size == shorthand.alphabet_size
    assert manual.num_states == shorthand.num_states