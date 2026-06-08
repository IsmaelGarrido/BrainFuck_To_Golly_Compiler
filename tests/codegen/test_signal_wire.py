"""
Brainfuck_To_Golly_Compiler/tests/codegen/test_signal_wire.py
----------------------------------
Unit tests for signal_wire.py.
"""

import sys, os
import pytest
from compiler.codegen.signal_wire import (
    SignalWire, Reflector, make_wire, make_sync_wire,
    SNARK_RECOVERY, DEFAULT_PERIOD, SNARK_PAIR_DELAY, SNARK_PAIR_DISTANCE
)
from compiler.codegen.pattern_lib import (
    GOSPER_GUN, EATER1, SNARK,
    GLIDER_SE, GLIDER_SW, GLIDER_NE, GLIDER_NW
)

def test_basic_construction():
    """SignalWire stores source and destination correctly."""
    w = SignalWire(0,0,100,100)
    assert w.x1 == 0 and w.y1 == 0
    assert w.x2 == 100 and w.y2 == 100

def test_default_orientation():
    """Default orientation is SE."""
    w = SignalWire(0, 0, 100, 100)
    assert w.orientation == GLIDER_SE

def test_default_with_gun_and_eater():
    """By default wire has gun and eater."""
    w = SignalWire(0, 0, 100, 100)
    assert w.with_gun == True
    assert w.with_eater == True

def test_no_reflectors_initially():
    """New wire has no reflectors."""
    w = SignalWire(0, 0, 100, 100)
    assert len(w.reflectors) == 0
    assert w._extra_delay == 0

def test_custom_orientation():
    """Wire accepts custom orientation"""
    w = SignalWire(0, 0 ,100, 100, orientation=GLIDER_NW)
    assert w.orientation == GLIDER_NW

def test_custom_period():
    """Wire accepts custom period."""
    w = SignalWire(0, 0, 100, 100, period = 60)
    assert w.period == 60

def test_base_travel_time_diagonal():
    """Diagonal travel: 1 cell = 4 generations."""
    w = SignalWire(0, 0, 10, 10)
    assert w.base_travel_time() == 40

def test_base_travel_time_zero():
    """Zero displacement = zero travel time."""
    w = SignalWire(50,50,50,50)
    assert w.base_travel_time() == 0

def test_base_travel_time_asymetric():
    """Uses max(|dx|, |dy|)."""
    w = SignalWire(0, 0, 5, 10)
    assert w.base_travel_time() == 40

def test_total_travel_time_no_delay():
    """Without delays, total equals base."""
    w = SignalWire(0, 0, 10, 10)
    assert w.total_travel_time() == w.base_travel_time()

def test_total_travel_time_with_delay():
    """With added delay. total = base + extra."""
    w = SignalWire(0, 0, 10, 10)
    w.add_delay(1)
    assert w.total_travel_time() == w.base_travel_time() + SNARK_PAIR_DELAY

def test_phase_at_destination_basic():
    """Phase is total_trave_time % period."""
    w = SignalWire(0, 0, 30, 30, period=30)
    assert w.phase_at_destination() == 0

def test_phase_at_destination_nonzero():
    """Phase is correctly computed for non-zero result."""
    w = SignalWire(0, 0, 10, 10, period=30)
    assert w.phase_at_destination() == 10

def test_delay_needed_same_phase():
    """No delay needed if already at target phase."""
    w = SignalWire(0, 0, 30, 30, period=30)
    assert w.delay_needed_for_phase(0) == 0

def test_delay_needed_wrap():
    """Delay needed wraps around period correctly."""
    w = SignalWire(0, 0, 10, 10, period=30)
    assert w.delay_needed_for_phase(5) == 25

def test_add_delay_adds_reflectors():
    """add_delay(1) adds 2 Snark reflectors."""
    w = SignalWire(0, 0, 200, 200)
    w.add_delay(1)
    assert len(w.reflectors) == 2

def test_add_delay_two_pairs():
    """add_delay(2) adds 4 Snark reflectors."""
    w = SignalWire(0, 0, 200, 200)
    w.add_delay(2)
    assert len(w.reflectors) == 4

def test_add_delay_increases_extra_delay():
    """add_delay increments _extra_delay by SNARK_PAIR_DELAY per pair."""
    w = SignalWire(0, 0, 200, 200)
    w.add_delay(1)
    assert w._extra_delay == SNARK_PAIR_DELAY

def test_add_delay_chaining():
    """add_delay returns self for method chaining."""
    w = SignalWire(0,0,200,200)
    result = w.add_delay(1)
    assert result is w

def test_add_reflector_manual():
    """add_reflector adds a single Snark at explicit coordinates."""
    w = SignalWire(0, 0, 200, 200)
    w.add_reflector(100, 100, turn='left')
    assert len(w.reflectors) == 1
    assert w.reflectors[0].x == 100
    assert w.reflectors[0].y == 100

def test_add_reflector_increases_delay():
    """Manual reflector adds SNARK_RECOVERY to extra delay."""
    w = SignalWire(0, 0, 200, 200)
    w.add_reflector(100, 100)
    assert w._extra_delay == SNARK_RECOVERY

def test_add_reflector_chaining():
    """add_reflector returns self for method chaining."""
    w = SignalWire(0, 0, 200, 200)
    result = w.add_reflector(100, 100)
    assert result is w

def test_add_delay_for_phase():
    """add_delay_for_phase adjust phase toward target."""
    w = SignalWire(0, 0, 10, 10, period = 30)
    initial_phase = w.phase_at_destination()
    w.add_delay_for_phase(initial_phase)
    assert w._extra_delay == 0

def test_add_delay_for_phase_zero_needed():
    """No delay added when already at target phase."""
    w = SignalWire(0, 0, 30, 30, period=30)
    w.add_delay_for_phase(0)
    assert w._extra_delay == 0

def test_pattern_with_gun_and_eater():
    """Pattern includes gun + eater population."""
    w = SignalWire(0, 0, 200, 200)
    p = w.pattern()
    expected = GOSPER_GUN.instantiate().population + EATER1.instantiate().population
    assert p.population == expected

def test_pattern_gun_only():
    """Pattern with only gun."""
    w = SignalWire(0, 0, 200, 200, with_eater=False)
    p = w.pattern()
    assert p.population == GOSPER_GUN.instantiate().population

def test_pattern_eater_only():
    """Pattern with only eater."""
    w = SignalWire(0, 0, 200, 200, with_gun=False)
    p = w.pattern()
    assert p.population == EATER1.instantiate().population

def test_pattern_none_when_empty():
    """Pattern returns None when no components."""
    w = SignalWire(0, 0, 200, 200, with_gun=False, with_eater=False)
    assert w.pattern() is None

def test_pattern_with_reflectors():
    """Pattern includes Snark population for each reflector."""
    w = SignalWire(0, 0, 200, 200)
    w.add_delay(1)
    p = w.pattern()
    expected = (GOSPER_GUN.instantiate().population +
                EATER1.instantiate().population +
                SNARK.instantiate().population * 2)
    assert p.population == expected

def test_pattern_gun_at_source():
    """Gun is placed at source coordinates."""
    w = SignalWire(50, 60, 200, 200, with_eater=False)
    p = w.pattern()
    assert p.bounding_box[0] == 50
    assert p.bounding_box[1] == 60

def test_info_keys():
    """info() returns all expected keys."""
    w = SignalWire(0, 0, 100, 100)
    d = w.info()
    expected_keys = {
        'source', 'destination', 'orientation', 'period',
        'base_travel_time', 'extra_delay', 'total_travel_time',
        'arrival_phase', 'n_reflectors'
    }
    assert set(d.keys()) == expected_keys

def test_info_values_consistent():
    """info() values are consistent with wire properties."""
    w = SignalWire(0, 0, 10, 10)
    d = w.info()
    assert d['source']            == (0, 0)
    assert d['destination']       == (10, 10)
    assert d['base_travel_time']  == w.base_travel_time()
    assert d['total_travel_time'] == w.total_travel_time()
    assert d['arrival_phase']     == w.phase_at_destination()
    assert d['n_reflectors']      == len(w.reflectors)
 
def test_repr():
    """repr includes key information."""
    w = SignalWire(0, 0, 10, 10)
    r = repr(w)
    assert 'SignalWire' in r
    assert '0' in r
 
def test_make_wire_basic():
    """make_wire creates a wire with correct properties."""
    w = make_wire(0, 0, 100, 100)
    assert w.x1 == 0 and w.y1 == 0
    assert w.x2 == 100 and w.y2 == 100
    assert w.with_gun  == True
    assert w.with_eater == True
 
def test_make_wire_custom_params():
    """make_wire passes through custom parameters."""
    w = make_wire(10, 20, 100, 200, orientation=GLIDER_NW, period=60)
    assert w.orientation == GLIDER_NW
    assert w.period == 60
 
def test_make_sync_wire_no_delay_needed():
    """make_sync_wire with matching phase adds no delay."""
    # Wire with travel time = 0 → phase = 0
    w = make_sync_wire(0, 0, 0, 0, target_phase=0)
    assert w._extra_delay == 0
 
def test_make_sync_wire_returns_signal_wire():
    """make_sync_wire returns a SignalWire instance."""
    w = make_sync_wire(0, 0, 100, 100)
    assert isinstance(w, SignalWire)
 
 
# ── REFLECTOR DATACLASS ───────────────────────────────────────────────────────
 
def test_reflector_construction():
    """Reflector stores coordinates and turn direction."""
    r = Reflector(x=100, y=200, turn='right')
    assert r.x == 100
    assert r.y == 200
    assert r.turn == 'right'
 
def test_reflector_default_delay():
    """Reflector has default delay of SNARK_PAIR_DELAY."""
    r = Reflector(x=0, y=0)
    assert r.delay_added == SNARK_PAIR_DELAY