"""
Brainfuck_To_Golly_Compiler/tests/semantic/test_tm_encoder.py
-----------------------------------------------
Unit Test for encoder module
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'compiler', 'source'))

import pytest
from compiler.semantic.tm_encoder import(
    encode, encode_source, Transition, TMProgram,
    EncoderError, ALPHABET, ALPHABET_SIZE
)

def enc(source: str) -> TMProgram:
    return encode_source(source)

def test_alphabet_size():
    """Full BF alphabet has 256 symbols."""
    assert ALPHABET_SIZE == 256
    assert len(ALPHABET) == 256

def test_alphabet_range():
    """Alphabet covers exactly 0..255."""
    assert ALPHABET[0] == 0
    assert ALPHABET[-1] == 255

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
    """'<' generates L transitions."""
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
    for sym in range(1, 256):
        t = tm.transition_for(tm.initial_state, sym)
        assert t.write == sym -1, f"Expected {sym-1} for symbol {sym}, got {t.write} instead"

def test_decrements_wraps_at_zero():
    """'-' wraps 0 to 255."""
    tm = enc('-')
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

def test_sequence_state_count():
    """N simple instructions generate N+2 states, 1 initial, N instructions and an accept state."""
    for n, src in enumerate(['+', '++', '+++', '++++'], start=1):
        tm = enc(src)
        assert tm.num_states == n+2, f"{src!r}: expected {n+2} states, got {tm.num_states}."

def test_empty_loop_symbol_zero_skips_body():
    """'[]' reading 0 at loop entry jumps to post-loop state."""
    tm = enc('[]')
    t = tm.transition_for(tm.initial_state, 0)
    assert t is not None
    assert t.new_state != tm.initial_state

def test_empty_loop_symbol_nonzero_loops():
    """'[] reading non-zero at loop entry loops back."""
    tm = enc('+[]')
    loop_entry = tm.transitions_from(tm.initial_state)[0].new_state
    t = tm.transition_for(loop_entry, 1)
    assert t is not None
    assert t.new_state != tm.accept_state


def test_simple_loop_zero_exits():
    """'[-]' symbol 0 at loop entry jumps to loop_exit(post-loop state)"""
    tm = enc('[-]')
    t_zero = tm.transition_for(tm.initial_state, 0)
    assert t_zero is not None
    assert t_zero.new_state != tm.initial_state
    loop_exit = t_zero.new_state
    exit_transitions = tm.transitions_from(loop_exit)
    assert len(exit_transitions) > 0

def test_simple_loop_nonzero_enters_body():
    """'[-]' symbol != 0 at loop entry enters body."""
    tm = enc('[-]') 
    t_one = tm.transition_for(tm.initial_state, 1)
    assert t_one is not None
    assert t_one.new_state != tm.accept_state
    assert t_one.new_state != tm.initial_state   

def test_loop_entry_preserves_symbol():
    """Loop entry evaluation does not modify the tape symbol."""
    tm = enc('[+]')
    for sym in range(256):
        t = tm.transition_for(tm.initial_state, sym)
        assert t is not None
        assert t.read == t.write

def test_nested_loop_is_deterministic():
    """Nested loops produce a deterministic table."""
    assert enc('[[+]]').is_deterministic()

def test_deep_nested_loop_is_deterministic():
    """Three levels of nesting produce a deterministic table."""
    assert enc('[[[+]]]').is_deterministic()

def test_loop_more_states_than_flat():
    """A loop generates more states than the equivalent flat sequence."""
    assert enc('[+-]').num_states > enc('+-').num_states

def test_transitions_from_filters_correctly():
    """transitions_from return only transitios from the given state."""
    tm = enc('++')
    for state in range(tm.num_states):
        for t in tm.transitions_from(state):
            assert t.state == state

def test_transition_for_returns_correctly():
    """transition_for returns the transition matching(state, symbol)."""
    tm = enc('+')
    t = tm.transition_for(0,5)
    assert t is not None
    assert t.state == 0
    assert t.read == 5
    assert t.write == 6

def test_transition_for_returns_none_for_accept():
    """transition_for returns None for a state with no outgoing transitions."""
    tm = enc('+')
    result = tm.transition_for(tm.accept_state, 0)
    assert result is None

def test_add_program():
    """'++>+++<[->+<]' encodes correctly and is deterministic."""
    tm = enc('++>+++<[->+<]')
    assert tm.is_deterministic()
    assert tm.initial_state == 0
    assert tm.accept_state == tm.num_states -1

def test_counter_program():
    """'+++++[-]' encodes correctly."""
    assert enc('+++++[-]').is_deterministic()

def test_copy_program():
    """'+++[->+<]' encodes correctly."""
    assert enc('+++[->+<]').is_deterministic()

def test_multiplication_program():
    """Multiplication program encodes correctly."""
    assert enc('+++>++>[-]>[-]<<<[>[->+>+<<]>>[-<<+>>]<<<-]>>').is_deterministic()

def test_Q_contains_all_states():
    """Q contains every single state referenced in the transition table."""
    tm = enc('++>[-]')
    Q = tm.Q
    for t in tm.transitions:
        assert t.state in Q
        assert t.new_state in Q

def test_Q_contains_initial_and_accept():
    """Q always contains q0 and q_accept."""
    tm = enc('+')
    assert tm.initial_state in tm.Q
    assert tm.accept_state in tm.Q

def test_Q_size_matches_num_states():
    """Size of Q equals num_states."""
    for src in ('', '+', '[-]', '++>+++<[->+<]'):
        tm = enc(src)
        assert len(tm.Q) == tm.num_states, f"{src!r}: |Q|={len(tm.Q)} but num_states={tm.num_states}"

def test_tape_alphabet_full_bf():
    """tape_alphabet covers 0.255 for a program that uses all value."""
    tm = enc('+')
    gamma = tm.tape_alphabet
    assert 0 in gamma
    assert 255 in gamma
    assert len(gamma) == 256

def test_tape_alphabet_subset_of_bf_range():
    """All symbols in tape_alphabet are within 0..255."""
    tm = enc("++>[-]<.")
    for sym in tm.tape_alphabet:
        assert 0 <= sym <= 255

def test_input_alphabet_subset_of_tape_alphabet():
    """Σ ⊆ Γ — input alphabet is a subset of tape alphabet."""
    tm = enc('++[-]')
    assert tm.input_alphabet <= tm.tape_alphabet

def test_as_formal_tuple_keys():
    """as_formal_tuple returns all required 7-tuple components."""
    tm = enc('+')
    d = tm.as_formal_tuple()
    assert 'Q' in d
    assert 'Sigma' in d
    assert 'Gamma' in d
    assert 'q0' in d
    assert 'q_accept' in d
    assert 'num_transitions' in d

def test_as_formal_tuple_values():
    """as_formal_tuple values are consistent with TMProgram fields."""
    tm = enc('+')
    d = tm.as_formal_tuple()
    assert d['q0'] == tm.initial_state
    assert d['q_accept'] == tm.accept_state
    assert d['num_transitions'] == len(tm.transitions)
    assert d['Q'] == tm.Q
    assert d['Gamma'] == tm.tape_alphabet

def test_formal_tuple_Q_equals_Q_property():
    """as_formal_tuple['Q'] matches the Q property."""
    tm = enc('+++[->+<]')
    assert tm.as_formal_tuple()['Q'] == tm.Q