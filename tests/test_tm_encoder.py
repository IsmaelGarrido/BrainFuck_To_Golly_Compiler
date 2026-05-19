"""
Brainfuck_To_Golly_Compiler/tests/test_tm_encoder.py
-----------------------------------------------
Unit Test for encoder module
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'compiler', 'source'))

import pytest
from tm_encoder import(
    encode, encode_source, Transition, TMProgram,
    EncoderError, ALPHABET, ALPHABET_SIZE
)

def enc(source: str) -> TMProgram:
    return encode_source(source)

def transitions_for_state(tm: TMProgram, state: int) -> list[Transition]:
    return tm.transition_from(state)

def test_alphabet_size():
    """Full BF alphabet has 256 symbols."""
    assert ALPHABET_SIZE == 256
    assert len(ALPHABET) == 256

def test_alphabet_range():
    """Alphabet covers exactly 0..255."""
    assert ALPHABET[0] == 0
    assert ALPHABET[-1] == 256

def test_empty_program_structure():
    """Empty program produces valid TMProgram."""
    tm = enc('')
    assert tm.initial_state == 0
    assert tm.accept_state > tm.initial_state
    assert tm.num_states >= 2
    assert isinstance(tm.transitions, list)

def test_initial_state_is_zero():
    """Initial state is always 0."""
    for src in ('+','++','[+]', '><'):
        assert enc(src).initial_state == 0

def test_accept_state_is_last():
    """Accept state is always num_states -1."""

    for src in ('+', '++', '[-]', '><'):
        tm = enc(src)
        assert tm.accept_state == tm.num_states - 1

def test_alphabet_size_in_result():
    """TMProgram reports alphabet_size = 256."""
    assert enc('+').alphabet_size==256

def test_symbols_in_range():
    """All read and write symbols are in 0..255."""
    tm = enc('++>--<')
    for t in tm.transitions:
        assert 0 <= t.read <= 255
        assert 0 <= t.write <= 255

def test_directions_valid():
    """All directions are L, R or N."""
    tm = enc('><+-.')
    for t in tm.transitions:
        assert t.direction in ('L', 'R', 'N')

def test_is_deterministic():
    """Every generated table is deterministic."""
    for src in ('', '+', '-','>','<','.','[-]','++>+++<[->+<]', '[[-]]'):
        tm = enc(src)
        assert tm.is_deterministic(), f"Non-deterministic for: {src!r}"

def test_simple_instruction_generates_256_transitions():
    """Each simple instructions generates exactly 256 transitions from its state."""
    for op in ('>', '<', '+', '-', '.'):
        tm = enc(op)
        entry = tm.transitions_from(tm.initial_state)
        assert len(entry) == 256, f"'{op}': expected 256 transitions, got {len(entry)}"

def test_each_symbol_has_exactly_one_transition():
    """From any instruction state, each symbol has exactly one transition."""
    tm = enc('+-><.')
    for state in range(tm.num_states -1):
        state_transitions = tm.transitions_from(state)
        if not state_transitions:
            continue
        symbols = [t.read for t in state_transitions]
        assert len(symbols) == len(set(symbols)), f"Duplicate symbols in {state}"

def test_move_right_direction():
    """'>' generates R transitions."""
    tm = enc('>')
    for t in tm.transitions_from(tm.initial_state):
        assert t.direction == 'R'

def test_move_left_direction():
    """'>' generates L transitions."""
    tm = enc('<')
    for t in tm.transitions_from(tm.initial_state):
        assert t.direction == 'L'

def test_move_preserves_symbol():
    """'>' and '<' do not modify the symbol."""
    for op in ('>', '<'):
        tm = enc(op)
        for t in tm.transitions_from(tm.initial_state):
            assert t.read == t.write

def test_increments_adds_one():
    """'+' writes sym+1 for symbols 0..254."""
    tm = enc('+')
    for sym in range(255):
        t = tm.transition_for(tm.initial_state, sym)
        assert t.write == sym +1, f"Expected {sym+1} for symbol {sym}, got {t.write} instead"

def test_increments_wraps_at_255():
    """'+' wraps 255 to 0."""
    tm = enc('+')
    t = tm.transition_for(tm.initial_state, 255)
    assert t.write == 0

def test_decrements_subtracts_one():
    """'-' writes sym-1 for symbols 1..255."""
    tm = enc('-')
    for sym in range(255):
        t = tm.transition_for(tm.initial_state, sym)
        assert t.write == sym -1, f"Expected {sym-1} for symbol {sym}, got {t.write} instead"

def test_decrements_wraps_at_zero():
    """'-' wraps 0 to 255."""
    tm = enc('+')
    t = tm.transition_for(tm.initial_state, 0)
    assert t.write == 255

def test_increment_decrement_no_head_movement():
    """'+' and '-' do not move the head."""
    for op in ('+', '-'):
        tm = enc(op)
        for t in tm.transitions_from(tm.initial_state):
            assert t.direction == 'N'

def test_output_flagger():
    """'.' transitions are flagged as is_output=True."""
    tm = enc('.')
    output_ts = [t for t in tm.transitions if t.is_output]
    assert len(output_ts) == 256

def test_output_preserves_symbol():
    """'.' does not modify the tape."""
    tm = enc('.')
    for t in tm.transitions:
        if t.is_output:
            assert t.read==t.write

def test_output_no_head_movement():
    """'.' does not move the head."""
    tm = enc('.')
    for t in tm.transitions:
        if t.is_output:
            assert t.direction == 'N'

def test_non_output_instructions_not_flagged():
    """'+', '-', '>', '<' are not flagged as output."""
    tm = enc('+-><')
    assert len(tm.output_transitions()) == 0

def test_input_raises_encoder_error():
    """',' raises EncoderError."""
    with pytest.raises(EncoderError):
        enc(',')

        