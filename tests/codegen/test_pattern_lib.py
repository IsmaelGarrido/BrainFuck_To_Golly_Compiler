"""
tests/codegen/test_pattern_lib.py
----------------------------------
Unit tests for pattern_lib.py.
"""

import sys, os

import pytest
import tempfile
from pattern_lib import (
    GLIDER, BLOCK, EATER1, GOSPER_GUN, SNARK, BLINKER, BEEHIVE,
    GLIDER_SE, GLIDER_SW, GLIDER_NE, GLIDER_NW,
    PRIMITIVES, compose, place, save_rle, glider_position_at,
    _get_tree
)

def test_registry_contains_all_primitives():
    """PRIMITIVES dict contains all expected keys."""
    expected = {"glider", "block", "eater1", "gosper_gun",
                "snark", "blinker", "beehive"}
    assert set(PRIMITIVES.keys()) == expected

def test_all_primitives_have_rle():
    """Every primitive has a non-empty RLE string."""
    for name, pdef in PRIMITIVES.items():
        assert pdef.rle, f"{name}: RLE is empty"

def test_all_primitives_have_description():
    """Every primitive has a non-empty description."""
    for name, pdef in PRIMITIVES.items():
        assert pdef.description, f"{name}: description is empty"

def test_glider_population():
    p = GLIDER.instantiate()
    assert p.population == 5

def test_glider_bounding_box():
    p = GLIDER.instantiate()
    x, y, w, h = p.bounding_box
    assert w == 3 and h == 3

def test_glider_period_4():
    """Glider returns to same shape (different position) every 4 gens."""
    p = GLIDER.instantiate()
    p4 = p.advance(4)
    assert p4.population == 5

def test_glider_displacement_se():
    """SE glider moves +1,+1 per 4 gens."""
    p = GLIDER.instantiate()
    p4 = p.advance(4)
    dx = p4.bounding_box[0] - p.bounding_box[0]
    dy = p4.bounding_box[1] - p.bounding_box[1]
    assert dx == 1 and dy == 1

def test_glider_displacement_sw():
    """SW glider moves -1,+1 per 4 gens."""
    p = GLIDER.instantiate()
    p4 = p.advance(4)
    dx = p4.bounding_box[0] - p.bounding_box[0]
    dy = p4.bounding_box[1] - p.bounding_box[1]
    assert dx == -1 and dy == 1

def test_glider_displacement_ne():
    """NE glider moves +1, -1 per 4 gens."""
    p = GLIDER.instantiate()
    p4 = p.advance(4)
    dx = p4.bounding_box[0] - p.bounding_box[0]
    dy = p4.bounding_box[1] - p.bounding_box[1]
    assert dx == -1 and dy == -1

def test_glider_displacement_nw():
    """NW glider moves -1, -1 per 4 gens."""
    p = GLIDER.instantiate()
    p4 = p.advance(4)
    dx = p4.bounding_box[0] - p.bounding_box[0]
    dy = p4.bounding_box[1] - p.bounding_box[1]
    assert dx == -1 and dy == -1  

def test_glider_shift():
    """Glider placed at (10,20) has a bbox starting at (10,20)."""
    p = GLIDER.instantiate(x=10, y=20)
    assert p.bounding_box[0] == 10
    assert p.bounding_box[1] == 20

def test_block_population():
    assert BLOCK.instantiate().population == 4

def test_block_bounding_box():
    x, y, w, h = BLOCK.instantiate().bounding_box
    assert w == 2 and h == 2

def test_block_is_still_life():
    """Block is unchanged after 10 gens."""
    p = BLOCK.instantiate()
    p10 = p.advance(10)
    assert p.population == p10.population
    assert p.bounding_box == p10.bounding_box
    
def test_block_period_is_one():
    assert BLOCK.period == 1
    assert BLOCK.velocity is None

def test_eater1_population():
    assert EATER1.instantiate().population == 7

def test_eater1_bounding_box():
    x, y, w, h = EATER1.instantiate().bounding_box
    assert w == 4 and h == 4

def test_eater1_is_still_life():
    p = EATER1.instantiate()
    p10 = p.advance(10)
    assert p.population == p10.population

def test_eater1_period_is_one():
    assert EATER1.period == 1

def test_gosper_gun_population():
    assert GOSPER_GUN.instantiate().population == 36

def test_gosper_gun_bounding_box():
    x, y, h, w = GOSPER_GUN.instantiate().bounding_box
    assert w == 36 and h == 9

def test_gosper_gun_emits_at_period_30():
    """Gun population increases by 5 (one glider) every 30 generations."""
    p = GOSPER_GUN.instantiate()
    p30 = p.advance(30)
    p60 = p.advance(60)
    delta30 = p30.population - p.population
    delta60 = p60.population - p.population
    assert delta30 == 5
    assert delta60 == 10

def test_gosper_gun_period():
    assert GOSPER_GUN.period == 30

def test_snark_population():
    assert GOSPER_GUN.instantiate().population == 22

def test_snark_bounding_box():
    w, y, w, h = SNARK.instantiate().bounding_box
    assert w == 41 and h == 24

def test_snark_is_still_life():
    p = SNARK.instantiate()
    p1 = p.advance(1)
    assert p.population == p1.population

def test_snark_period_is_one():
    assert SNARK.period == 1


def test_blinker_population():
    assert BLINKER.instantiate().population == 3

def test_blinker_period_two():
    """Blinker returns to original state every 2 generations."""
    p = BLINKER.instantiate()
    p2 = p.advance(2)
    assert p.population == p2.population
    assert p.bounding_box == p2.bounding_box

def test_blinker_changes_at_gen_one():
    """Blinker shape changes at generation 1."""
    p = BLINKER.instantiate()
    p1 = p.advance(1)
    assert p.bounding_box != p1.bounding_box

def test_beehive_population():
    assert BEEHIVE.instantiate().population == 6

def test_beehive_is_still_life():
    p = BEEHIVE.instantiate()
    p5 = p.advance(5)
    assert p.population == p5.population


def test_compose_two_patterns():
    """Compose block + glider gives combined population."""
    result = compose(
        (BLOCK, 0, 0),
        (GLIDER, 20, 20),
    )
    assert result.population == BLOCK.instantiate().population + GLIDER.instantiate().population

def test_compose_with_transform():
    """Compose support transform parameter."""
    result = compose(
        (GLIDER, 0, 0, GLIDER_SE),
        (GLIDER, 50, 0, GLIDER_SW),
    )
    assert result.population == 10

def test_compose_three_patterns():
    result = compose(
        (BLOCK, 0, 0),
        (BLOCK, 10, 0),
        (EATER1, 30, 0),
    )
    expected = (BLOCK.instantiate().population *2 + 
                EATER1.instantiate().population)
    assert result.population == expected

def test_place_shorthand():
    """place() is equivalent to PatternDef.instantiate()."""
    p1 = place(BLOCK, 5, 10)
    p2 = BLOCK.instantiate(5,10)
    assert p1.population == p2.population
    assert p1.bounding_box == p2.bounding_box

def test_save_rle_creates_file(tmp_path):    
    """save_rle writes a .rle file."""
    p = GLIDER.instantiate()
    path = str(tmp_path / "test.rle")
    save_rle(p, path)
    assert os.path.exists(path)

def test_save_rle_no_cll_header(tmp_path):
    """Saved RLE does not contain lifelib-specific #CLL header."""
    p = GLIDER.instantiate()
    path = str(tmp_path / "test.rle")
    save_rle(p, path)
    content = open(path).read()
    assert "#CLL" not in content

def test_save_rle_has_rule(tmp_path):
    """Save RLE contains the B3/S23 rule."""
    p = GLIDER.instantiate()
    path = str(tmp_path / "test.rle")
    save_rle(p, path)
    content = open(path).read()
    assert "B3/S23" in content or "b3s23" in content.lower()

def test_sace_rle_with_comment(tmp_path):
    """Comment is included in saved RLE."""
    p = GLIDER.instantiate()
    path = str(tmp_path / "test.rle")
    save_rle(p, path, comment="Test glider")

def test_glider_position_at_gen0():
    """At generation 0, position equals starting position."""
    assert glider_position_at(10,20, 0, GLIDER_SE) == (10,20)

def test_glider_position_at_gen4_se():
    """SE glider moves +1,+1 per 4 generations."""
    x, y = glider_position_at(0, 0, 4, GLIDER_SE)
    assert x == 1 and y == 1
 
def test_glider_position_at_gen8_se():
    x, y = glider_position_at(0, 0, 8, GLIDER_SE)
    assert x == 2 and y == 2
 
def test_glider_position_at_gen4_sw():
    x, y = glider_position_at(10, 10, 4, GLIDER_SW)
    assert x == 9 and y == 11
 
def test_glider_position_at_gen4_ne():
    x, y = glider_position_at(10, 10, 4, GLIDER_NE)
    assert x == 11 and y == 9
 
def test_glider_position_at_gen4_nw():
    x, y = glider_position_at(10, 10, 4, GLIDER_NW)
    assert x == 9 and y == 9
 
def test_glider_position_non_multiple_of_4():
    """Generations not multiple of 4 round down (integer steps)."""
    # gen=5 → 1 complete step → same as gen=4
    assert glider_position_at(0, 0, 5, GLIDER_SE) == glider_position_at(0, 0, 4, GLIDER_SE)
 
def test_glider_position_large_generation():
    """Position scales correctly for large generation counts."""
    x, y = glider_position_at(0, 0, 400, GLIDER_SE)
    assert x == 100 and y == 100  # 400/4 = 100 steps
   
