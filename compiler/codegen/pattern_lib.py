"""
BrainFuck_To_Golly_Compiler/compiler/codegen/pattern_lib.py
---------------------------------
Library of GoL primitives used by the GoL generator.
"""

from dataclasses import dataclass, field
from typing import Optional
import lifelib

_session = None
_tree = None

def _get_tree():
    """
    Lazy-initialise the lifelib session.
    Called only when a pattern is first instatiated.
    """
    global _session, _tree
    if _tree is None:
        _session = lifelib.load_rules("b3s23")
        _tree = _session.lifetree(memory=200)
    return _tree

@dataclass
class PatternDef:
    """
    Definition of a GoL primitive pattern.
    
    Attributes:
        rle: RLE string (without header - data only)
        period: oscillation period in generations.
        velocity: (dx, dy) displacement per period, or None for stationary.
        safe_margin: minimum clearance to adjacent patterns (cells)
        description: role in the Turing Machine
    """
    rle: str
    period: int
    velocity: Optional[tuple[int, int]]
    safe_margin: int
    description: str

    def instantiate(self, x: int = 0, y: int = 0, transform: str = "identity"):
        """
        Create a lifelib Pattern object for this primitive.
        
        Parameters:
            x, y: positoin of the pattern's top-left corner
            transform: one of 'identity', 'flip_x', 'flip',
                        'rot90', 'rot270', 'rot180', 'transpose',
                        'swap_xy', 'swap_xy_flip', 'rcw', 'rccw'
        
        Returns:
            lifelib Pattern positioned at (x,y) with the given transform.
        """

        tree = _get_tree()
        p = tree.pattern(self.rle)
        if transform != "identity":
            p = p.transform(transform)
        if x != 0 or y != 0:
            p = p.shift(x,y)
        return p
    
GLIDER = PatternDef(
    rle = "bo$2bo$3o!",
    period = 4,
    velocity = (1,1),
    safe_margin = 5,
    description = (
        "Elementary spaceship - the basic unit of signal in the TM."
        "Presence = bit 1, absence = bit 0."
        "Default orientation: SE (dx=+1, dy=+1 per 4 generations)."
    )
)

GLIDER_SE = "identity"
GLIDER_SW = "flip_x"
GLIDER_NE = "flip_y"
GLIDER_NW = "flip"

BLOCK = PatternDef(
    rle = "2o$2o!",
    period = 1,
    velocity = None,
    safe_margin = 3,
    description = (
        "2x2 still life - 1-bit memory cell of the TM tape."
        "A block at the position i encodes tape[i] = 1."
        "Absence of a block encodes tape[i] = 0."
    )
)

EATER1 = PatternDef(
    rle = "2o$bo$bobo$2b2o!",
    period = 1,
    velocity = None,
    safe_margin = 6,
    description = (
        "4x4 still life - absorbs an incoming glider without being disturbed."
        "Recovery: immediate (still life returns to original state after absorption)."
        "Used to terminate signal channels and isolate modules."
    )
)

GOSPER_GUN = PatternDef(
    rle =   ("24bo$22bobo$12b2o6b2o12b2o$11bo3bo4b2o12b2o$"
             "2o8bo5bo3b2o$2o8bo3bob2o4bobo$"
             "10bo5bo7bo$11bo3bo$12b2o!"),
    period = 30,
    velocity = None,
    safe_margin = 20,
    description = (
        "Period-30 glider gun — emits one SE glider every 30 generations. "
        "Bounding box: 36×9 cells. "
        "Used as the clock source for signal channels in the TM. "
        "Each emitted glider carries a binary 1 on the signal wire."
    )
)

SNARK = PatternDef(
    rle         = ("3b2o$3b2o5$b2o$obo$2o7$"
                   "33b2o$32bobo$32bo$31b2o3$"
                   "38b3o$38bo$39bo!"),
    period      = 1,
    velocity    = None,
    safe_margin = 15,
    description = (
        "The most compact known stable glider reflector (discovered 2013). "
        "Deflects an incoming glider 90° (left turn). "
        "Recovery time: 43 generations between consecutive gliders. "
        "Bounding box: 41×24 cells. "
        "Used for routing signals between modules not in line-of-sight."
    )
)

BLINKER = PatternDef(
    rle = "3o!",
    period = 2,
    velocity = None,
    safe_margin = 4,
    description = (
        "Simplest oscillator (period 2). "
        "Alternates between a 3×1 horizontal bar and a 1×3 vertical bar. "
        "Used as a synchronisation marker or phase indicator."
    )
)

BEEHIVE = PatternDef(
    rle = "b2o$o2bo$b2o!",
    period = 1,
    velocity = None,
    safe_margin = 3,
    description = (
        "6-cell still life. "
        "Used as an alternative memory marker when block placement "
        "would interfere with adjacent channels."
    )
)

PRIMITIVES: dict[str, PatternDef] = {
    "glider":     GLIDER,
    "block":      BLOCK,
    "eater1":     EATER1,
    "gosper_gun": GOSPER_GUN,
    "snark":      SNARK,
    "blinker":    BLINKER,
    "beehive":    BEEHIVE,
}

def compose(*placements) -> object:
    """
    Compose multiple placed patterns into a single lifelib Pattern.
    
    Parameters:
        *placements: tuples of (PatternDef, x, y) or
                     (PatternDef, x, y, transform)
                     
    Returns:
        A sigle lifelib Pattern combining all placements.
    """
    result = None
    for placement in placements:
        if len(placement) == 3:
            pdef, x, y = placement
            transform = "identity"
        else:
            pdef, x, y, transform = placement

        p = pdef.instantiate(x, y, transform)
        result = p if result is None else result + p
    return result

def place(pdef: PatternDef, x: int, y: int, transform: str = "identity") -> object:
    """
    Shorthand for placing a single primitive at (x, y).
    Returns a lifelib Pattern.
    """
    return pdef.instantiate(x, y, transform)

def save_rle(pattern, path: str, comment: str = "") -> None:
    """
    Save a lifelib Pattern to a .rle file compatible with Golly.
    
    Strips all the lifelib-specific headers and replaces it with an optional comment line.
    
    Parameters:
        pattern:    lifelib Pattern object
        path:       output file path (.rle)
        comment:    optional comment to include in the file header
    """
    rle_str = pattern.rle_string()
    lines = rle_str.split('\n')
    clean = [l for l in lines if not l.startswith('#CLL')]
    if comment:
        clean.insert(0, f"#C {comment}")
    with open(path, "w") as f:
        f.write('\n'.join(clean))


def glider_position_at(x0: int, y0: int, generation: int,
                       orientation: str = GLIDER_SE) -> tuple[int, int]:
    """
    Calculate the bounding box origin of a glider at a given generation.
    
    Useful for synchronisation: given a glider starting at (x0, y0), 
    determine its position after N gens to ensure correct phase alignment
    with other components.
    
    Parameters:
        x0, y0:         starting top-left corner of the glider's bounding box
        generation:     number of generations passed
        orientation:    one of GLIDER_SE, GLIDER_SW, GLIDER_NE, GLIDER_NW
        
    Returns:
        (x, y) - bounding box origin of the glider at the given gen.
    """
    steps = generation // 4
    dx_map = {GLIDER_SE: +1, GLIDER_SW: -1, GLIDER_NE: +1, GLIDER_NW: -1}
    dy_map = {GLIDER_SE: +1, GLIDER_SW: +1, GLIDER_NE: -1, GLIDER_NW: -1}
    return (x0 + steps * dx_map[orientation],
            y0 + steps * dy_map[orientation])