"""
Brainfuck_To_Golly_Compiler/tests/validation/test_interpreter.py
------------------------
Unit tests of interpreter
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "compiler", "source"))

import pytest
from compiler.validation.interpreter import(
    run, interpret, InterpreterResult,
    InterpreterError, InputNotSupportedError, TapeUnderflowError
)

def tape(source):
    return run(source).tape

def out(source):
    return run(source).output

def ptr(source):
    return run(source).pointer

def test_empty_program():
    """Empty program returns zero-filled tape"""
    r = run('')
    assert r.tape[0] == 0
    assert r.output == []
    assert r.pointer == 0

def test_simple_increment():
    assert tape('+')[0] == 1

def test_multiple_increments():
    assert tape('+++++') [0] == 5

def test_simple_decrease():
    assert tape('++-')[0] == 1

def test_move_right():
    assert ptr('>') == 1

def test_move_left():
    assert ptr('><') == 0

def test_write_right_cell():
    r = run('>+')
    assert r.tape[0] == 0
    assert r.tape[1] == 1
    assert r.pointer == 1

def test_return_and_read_original_cell():
    r = run('>+++<')
    assert r.tape[0] == 0
    assert r.tape[1] == 3
    assert r.pointer == 0

def test_cell_overflow():
    """255 + 1 = 0 (wrap-around module 256)."""
    r = run('+' * 256)
    assert r.tape[0] == 0

def test_cell_underflow():
    """0 - 1 = 255 (wrap-around module 256)."""
    assert tape('-')[0] == 255

def test_underflow_and_overflow():
    r = run('-+')
    assert r.tape[0] == 0

def test_loop_does_not_execute_if_cell_zero():
    r = run('[+]')
    assert r.tape[0] == 0

def test_loop_sets_cell_to_zero():
    assert tape('+++++[-]')[0] == 0

def test_empty_loop():
    r = run('[]')
    assert r.tape[0] == 0

def test_nested_loop():
    """Nested loops: multiply 3x2 in cell[2]."""
    r = run('+++>++>[-]>[-]<<<[>[->+>+<<]>>[-<<+>>]<<<-]>>')
    assert r.tape[2] == 6

def test_simple_output():
    r = run('+.')
    assert r.output == [1]

def test_multiple_output():
    r = run('+++.+.')
    assert r.output == [3, 4]

def test_output_as_str():
    """65 = 'A', 66 = 'B'"""
    r = run('+' * 65 + '.' + '+.')
    assert r.output_as_str() == 'AB'

def test_tape_nonzero():
    r = run('+++>++')
    nz = r.tape_nonzero()
    assert nz[0] == 3
    assert nz[1] == 2

def test_add():
    """Adds 2+3 = 5. Result in cell[1]"""
    r = run('++>+++<[->+<]')
    assert r.tape[1] == 5

def test_regressive_counter():
    assert tape('+++++[-]')[0] == 0

def test_copy_cell():
    """Copies cell[0] into cell[1]"""
    r = run('+++[->+<]')
    assert r.tape[0] == 0
    assert r.tape[1] == 3

def test_input_not_supported():
    with pytest.raises(InputNotSupportedError):
        run(',')

def test_pointer_out_of_bounds_left():
    with pytest.raises(TapeUnderflowError):
        run('<')

def test_infinite_loop_detected():
    with pytest.raises(InterpreterError):
        run('+[]', max_steps=1000)

def test_steps_limit_configurable():
    r = run('+++++', max_steps=10)
    assert r.tape[0] == 5

def test_tape_expansion():
    """Tape expands when pointer surpases initial tape_size."""
    r = run('>' * 5 + '+', tape_size=3)
    assert r.tape[5] == 1
    assert r.pointer == 5