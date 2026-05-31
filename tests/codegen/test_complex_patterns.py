"""
Brainfuck_To_Golly_Compiler/tests/codegen/test_complex_patterns.py
--------------------------------------------------------------------
Unit tests for complex_patterns.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'compiler', 'codegen'))

import pytest
from compiler.codegen.complex_patterns import (
    travel_time, phase_offset, glider_channel, signal_delay, memory_cell,
    memory_cell_write, fanout, and_gate, or_gate, conditional_branch, tape_segment
)

from compiler.codegen.pattern_lib import (
    GOSPER_GUN, EATER1, SNARK, BLOCK, GLIDER,
    GLIDER_SE, GLIDER_SW, GLIDER_NE, GLIDER_NW
)

def test_travel_time_diagonal():
    """Diagonal travel: 1 cell = 4 gens."""
    assert travel_time(1,1) == 4

def test_travel_time_10_cells():
    """10 diagonal cells = 40 gens."""
    assert travel_time(10,10) == 40

def test_travel_time_asymetric():
    """Uses max(|dx|, |dy|) for diagonal distance."""
    assert travel_time(5,10) == 40

def test_travel_time_zero():
    assert travel_time(0, 0) == 0

def test_phase_offset_basic():
    """Phase offset wraps at period."""
    assert phase_offset(0,30) == 0
    assert phase_offset(30,30) == 0
    assert phase_offset(15,30) == 15
    assert phase_offset(31, 30) == 1

def test_phase_offset_custom_period():
    assert phase_offset(10,60) == 10
    assert phase_offset(60,60) == 0

def test_glider_channel_with_gun_and_eater():
    """Channel with gun and eater has correct population."""
    p = glider_channel(0, 0, 100, 100)
    expected = GOSPER_GUN.instantiate().population + EATER1.instantiate().population
    assert p.population == expected

def test_glider_channel_gun_only():
    """Channel with only gun has gun population."""
    p = glider_channel(0,0, 100, 100, with_gun=True, with_eater=False)
    assert p.population == GOSPER_GUN.instantiate().population

def test_glider_channel_eater_only():
    """Channel with only eater has eater population."""
    p = glider_channel(0, 0, 100, 100, with_gun=False, with_eater=True)
    assert p.population == EATER1.instantiate().population

def test_glider_channel_none():
    """Channel with no components returns None."""
    p = glider_channel(0, 0 ,100,100, with_gun=False, with_eater=False)
    assert p is None

def test_glider_channel_gun_at_source():
    """Gun is placed at source coordinates."""
    p = glider_channel(50, 60, 200, 200, with_gun = True, with_eater = False)
    assert p.bounding_box[0] == 50
    assert p.bounding_box[1] == 60

def test_signal_delay_one_pair():
    """One reflector pair places 2 Snarks."""
    p = signal_delay(0, 0, n_reflectors = 1)
    expected = SNARK.instantiate().population * 2
    assert p.population == expected

def test_signal_delay_two_pairs():
    """Two reflector pairs place 4 Snarks."""
    p = signal_delay(0, 0 , n_reflectors = 2)
    expected = SNARK.instantiate().population * 4
    assert p.population == expected

def test_signal_delay_position():
    """First Snark is at the given coordinates."""
    p = signal_delay(100, 200, n_reflectors=1)
    assert p.bounding_box[0] <= 100
    assert p.bounding_box[1] <= 200

def test_memory_cell_initial_zero():
    """Memory cell with initial=0 has no block"""
    p = memory_cell(100, 100, initial=0)
    expected = EATER1.instantiate().population + SNARK.instantiate().population
    assert p.population == expected

def test_memory_cell_initial_one():
    """Memory cell with initial=1 includes a block."""
    p = memory_cell(100, 100, initial=1)
    expected = (EATER1.instantiate().population +
                SNARK.instantiate().population + 
                BLOCK.instantiate().population)
    assert p.population == expected

def test_memory_cell_initial_one_has_more_cells():
    """Cell with initial=1 has more cells than initial = 0."""
    p0 = memory_cell(100, 100, initial=0)
    p1 = memory_cell(100, 100, initial=1)
    assert p1.population > p0.population

def test_memory_cell_write_zero():
    """write_pattern(0) produces glider + eater."""
    p = memory_cell_write(100, 100, 0)
    assert p is not None
    assert p.population > 0

def test_memory_cell_write_one():
    """write_pattern(0) produces a block."""
    p = memory_cell_write(100, 100, 1)
    assert p.population == BLOCK.instantiate().population

def test_memory_cell_write_one_at_correct_position():
    """Block is placed at the cell coordinates."""
    p = memory_cell_write(100, 200, 1)
    assert p.bounding_box[0] == 100
    assert p.bounding_box[1] == 200

def test_memory_cell_write_invalid():
    """write_pattern rejects values other than 0 or 1."""
    with pytest.raises(ValueError):
        memory_cell_write(0,0,2)
    with pytest.raises(ValueError):
        memory_cell_write(0, 0, -1)

def test_fanout_has_snark_and_gun():
    """Fanout places a Snark and a Gosper Gun."""
    p = fanout(0, 0)
    expected = SNARK.instantiate().population + GOSPER_GUN.instantiate().population
    assert p.population == expected

def test_fanout_at_correct_position():
    """Fanout Snark starts at the given coordinates."""
    p = fanout(50, 100)
    assert p.bounding_box[0] <= 50
    assert p.bounding_box[1] <= 100

def test_and_gate_has_two_eaters():
    """AND gate places two Eater-1s."""
    p = and_gate(100, 100)
    expected = EATER1.instantiate().population * 2
    assert p.population == expected

def test_and_gate_eaters_near_collision_point():
    """AND gate eaters are close to the collision point."""
    p = and_gate(100,100)
    cx, cy, cw, ch = p.bounding_box

    assert abs(cx - 100) < 20
    assert abs(cy - 100) < 20

def test_or_gate_has_two_snarks():
    """OR gate places two Snarks."""
    p = or_gate(100, 100)
    expected = SNARK.instantiate().population * 2
    assert p.population == expected

def test_conditional_branch_components():
    """Conditional branch has glider + snark + eater."""
    p = conditional_branch(0, 0 , 50, 50)
    expected = (GLIDER.instantiate().population +
                SNARK.instantiate().population +
                EATER1.instantiate().population)
    assert p.population == expected

def test_conditional_branch_probe_at_source():
    """Probe glider starts at source coordinates."""
    p = conditional_branch(10, 10, 100, 100)
    assert p.bounding_box[0] <= 10
    assert p.bounding_box[1] <= 10


def test_tape_segment_blank():
    """Blank tape segment has Eaters and Snarks but no Blocks."""
    p = tape_segment(100, 100, num_cells = 3)
    expected = 3 * (EATER1.instantiate().population +
                    SNARK.instantiate().population)
    assert p.population == expected

def test_tape_segment_with_initial_ones():
    """Blank tape segment has Eaters and Snarks but no Block"""
    p = tape_segment(100, 100, num_cells = 3, initial_values={0:1, 2:1})
    extra = 2 * BLOCK.instantiate().population
    blank = 3 * (EATER1.instantiate().population +
                 SNARK.instantiate().population)
    assert p.population == blank + extra

def test_tape_segment_cell_spacing():
    """Cells are spaced correctly in the vertical direction."""
    spacing = 60
    p = tape_segment(100, 100, num_cells = 2, cell_spacing = spacing)
    h = p.bounding_box[3]
    assert h >= spacing

def test_tape_segment_single_cell():
    """Single cell tape has exactly one Eater + Snark."""
    p = tape_segment(0, 0, num_cells=1)
    expected = EATER1.instantiate().population + SNARK.instantiate().population
    assert p.population == expected