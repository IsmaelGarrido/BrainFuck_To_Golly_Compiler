"""
Brainfuck_To_Golly_Compiler/tests/codegen/test_tape.py
----------------------------------
Unit tests for tape.py.
"""

import sys, os
sys.path.insert(0,  os.path.join(os.path.dirname(__file__), '..', '..', 'compiler', 'codegen'))

import pytest
from compiler.codegen.tape import(
    Tape, TapeCell, make_tape, CELL_SPACING, TAPE_ORIGIN_X, TAPE_ORIGIN_Y,
    MIN_TAPE_CELLS, READ_PROBE_OFFSET, WRITE_GLIDER_OFFSET
)
from compiler.codegen.tape import SignalWire

def test_cell_spacing():
    assert CELL_SPACING == 60

def test_min_tape_cells():
    assert MIN_TAPE_CELLS >= 10

def test_tape_cell_coordinates():
    c = TapeCell(index=3, x=100, y=280)
    assert c.index == 3 and c.x == 100 and c.y == 280

def test_tape_cell_block_position():
    c = TapeCell(index=0, x=100, y=100)
    assert c.block_position == (100, 100)

def test_tape_cell_read_probe_origin():
    c = TapeCell(index = 0, x = 100, y = 100)
    px, py = c.read_probe_origin
    assert px == 100 - READ_PROBE_OFFSET
    assert py == 100

def test_tape_cell_write_origin():
    c = TapeCell(index=0, x = 100, y = 100)
    wx, wy = c.write_origin
    assert wx == 100 - WRITE_GLIDER_OFFSET
    assert wy == 100

def test_tape_cell_default_initial():
    assert TapeCell(index=0, x=0, y=0).initial == 0

def test_tape_cell_initial_one():
    assert TapeCell(index=0, x=0, y=0, initial=1).initial == 1

def test_tape_cell_invalid_initial():
    with pytest.raises(ValueError):
        TapeCell(index=0, x=0, y=0, initial=2)
    with pytest.raises(ValueError):
        TapeCell(index=0, x=0, y=0, initial=-1)

def test_tape_default_num_cells():
    assert len(Tape()) == MIN_TAPE_CELLS

def test_tape_all_cells_same_x():
    """Vertical tape - all cells share the same X."""
    tape = Tape()
    for cell in tape.cells:
        assert cell.x == TAPE_ORIGIN_X

def test_tape_cells_y_spacing():
    """Cell i is at Y = origin_y + i * cell_spacing."""
    tape = Tape()
    for i, cell in enumerate(tape.cells):
        assert cell.y == TAPE_ORIGIN_Y + i * CELL_SPACING

def test_tape_cell_indices():
    tape = Tape()
    for i, cell in enumerate(tape.cells):
        assert cell.index == i

def test_tape_custom_origin():
    tape = Tape(origin_x=300, origin_y=400)
    assert tape.cells[0].x == 300
    assert tape.cells[0].y == 400

def test_tape_custom_num_cells():
    assert len(Tape()) == MIN_TAPE_CELLS

def test_tape_extends_on_access():
    tape = Tape(num_cells=3)
    _ = tape.cell(5)
    assert len(tape) == 6

def test_extended_cell_coordinates():
    tape=Tape(num_cells=2)
    cell = tape.cell(4)
    assert cell.x == TAPE_ORIGIN_X
    assert cell.y == TAPE_ORIGIN_Y + 4 * CELL_SPACING

def test_access_within_bounds_no_extension():
    tape = Tape(num_cells=5)
    _ = tape.cell(3)
    assert len(tape) == 5

def test_position_of():
    tape = Tape()
    x, y = tape.position_of(0)
    assert x == TAPE_ORIGIN_X and y == TAPE_ORIGIN_Y

def test_y_of():
    tape = Tape()
    assert tape.y_of(0) == TAPE_ORIGIN_Y
    assert tape.y_of(1) == TAPE_ORIGIN_Y + CELL_SPACING
    assert tape.y_of(3) == TAPE_ORIGIN_Y + 3 * CELL_SPACING

def test_index_of_y_valid():
    tape = Tape()
    assert tape.index_of_y(TAPE_ORIGIN_Y) == 0
    assert tape.index_of_y(TAPE_ORIGIN_Y + CELL_SPACING) == 1
    assert tape.index_of_y(TAPE_ORIGIN_Y + 3 * CELL_SPACING) == 3

def test_index_of_y_invalid():
    tape = Tape()
    assert tape.index_of_y(TAPE_ORIGIN_Y + 1) is None
    assert tape.index_of_y(TAPE_ORIGIN_Y - CELL_SPACING) is None

def test_initial_pattern_blank_not_none():
    """Blank tape still has infraestructure (Eaters, Snarks)."""
    tape = Tape(num_cells=2)
    p = tape.initial_pattern({})
    assert p is not None

def test_initial_pattern_with_ones_has_more_cells():
    """Tape with initial=1 cells has more population than blank tape."""
    tape = Tape(num_cells=3)
    p_blank = tape.initial_pattern({})
    p_one = tape.initial_pattern({1:1})
    assert p_one.population > p_blank.population

def test_blank_tape_pattern():
    """blank_tape_pattern returns infrastructure pattern."""
    tape = Tape(num_cells=2)
    p = tape.blank_tape_pattern()
    assert p is not None

def test_read_wire_return_signal_wire():
    """read_wire returns a SignalWire instance."""
    tape = Tape()
    cell = tape.read_cell(0)
    w = tape.read_wire(0)
    px, py = cell.read_probe_origin
    assert w.x1 == px and w.y1 == py

def test_read_wire_destination_at_block():
    """Read wire destination is at the block position."""
    tape = Tape()
    cell = tape.cell(0)
    w = tape.read_wire(0)
    bx, by = cell.block_position
    assert w.x2 == bx, w.y2 == by

def test_read_wire_no_eater():
    """Read wire has no eater (eater is in memory cell infraestructure)."""
    tape = Tape()
    w = tape.read_wire(0)
    assert w.with_eater == False

def test_read_wire_has_gun():
    """Read wire has a gun at source."""
    tape = Tape()
    w = tape.read_wire(0)
    assert w.with_gun == True

def test_read_wire_different_cells():
    """Read wires for different cells have different coordinates."""
    tape = Tape()
    assert isinstance(tape.write_wire(0, 0), SignalWire)
    assert isinstance(tape.write_wire(0, 1), SignalWire)

def test_write_wire_zero_has_eater():
    """Write-0 wire has an eater (absorbs glider if no block)."""
    tape = Tape()
    w = tape.write_wire(0, 0)
    assert w.with_eater == True

def test_write_wire_one_no_eater():
    """Write-1 wire has no eater (places block directly)."""
    tape = Tape()
    w = tape.write_wire(0, 0)
    assert w.with_eater == True

def test_write_wire_one_no_eater():
    """Write-1 wire has no eater (places block directly)."""
    tape = Tape()
    w = tape.write_wire(0, 1)
    assert w.with_eater == False

def test_write_source_at_write_origin():
    """Write wire source is at the write origin of the cell."""
    tape= Tape()
    cell = tape.cell(0)
    w = tape.write_wire(0, 0)
    wx, wy = cell.write_origin
    assert w.x1 == wx and w.y1 == wy

def test_write_wire_invalid_value():
    """write_wire rejects values other than 0 or 1."""
    tape = Tape()
    with pytest.raises(ValueError):
        tape.write_wire(0, 2)

def test_write_wire_extends_tape():
    """write_wire on index beyond tape extends the tape."""
    tape = Tape(num_cells=3)
    tape.write_wire(7, 1)
    assert len(tape) >=8

def test_read_write_wire_custom_period():
    """Wires accept custom period parameter."""
    tape = Tape()
    w = tape.read_wire(0, period=60)
    assert w.period == 60

def test_make_tape_defaults():
    tape = make_tape()
    assert len(tape) == MIN_TAPE_CELLS
    assert tape.origin_x == TAPE_ORIGIN_X
    assert tape.origin_y == TAPE_ORIGIN_Y
    assert tape.cell_spacing == CELL_SPACING

def test_make_tape_custom():
    tape = make_tape(num_cells=5, origin_x=300, origin_y=400)
    assert len(tape) == 5
    assert tape.origin_x == 300
    assert tape.origin_y

def test_tape_repr():
    r = repr(make_tape())
    assert 'Tape' in r