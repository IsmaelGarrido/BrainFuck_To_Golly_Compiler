"""
BrainFuck_To_Golly_Compiler/compiler/codegen/complex_patterns.py
------------------------------------------------------------------
Composite GoL patterns for the Turing Machine Generator.
"""

from pattern_lib import (
    GLIDER, BLOCK, EATER1, GOSPER_GUN, SNARK, BLINKER,
    GLIDER_SE, GLIDER_SW, GLIDER_NE, GLIDER_NW,
    compose, place, glider_position_at, PatternDef, _get_tree
)

def travel_time(dx: int, dy: int) -> int:
    """
    Generations for a glider to travel diagonal distance.
    
    A glider moves 1 cell per 4 gens.
    
    Parameters:
        dx, dy: displacement in cells
        
    Returns:
        Number of generations for the glider to reach destination.
    """
    return max(abs(dx), abs(dy)) * 4

def phase_offset(gen: int, period: int = 30) -> int:
    """
    Calculate the phase of a glider stream at a given generation.
    
    Parameters:
        gen: generation count
        period: gun period (default 30 for gosper gun)
        
    Returns:
        Phase offset (0..period-1).
    """
    return gen % period


def glider_channel(x1: int, y1: int,
                   x2: int, y2: int,
                   orientation: str = GLIDER_SE,
                   with_gun: bool = True,
                   with_eater: bool = True):
    """
    A straight gilder signal channel form (x1, y1) to (x2, y2).
    
    Optionally includes a Gospen Gun at the source and an Eater-1
    at the sink to terminate gliders that are not intercepted.
    
    Paramenters:
        x1, y1: source coordinates (gun position)
        x2, y2: sink coordinates (eater position)
        orientation: glider direction (default SE)
        with_gun: if True, place a GosperGun at source
        with_eater: if True, place an Eater-1 at sink
    
    Returns:
        lifelib Pattern with the channel infraestructure.

    Note:
        The channel itself is implicit - gliders travel through empty
        space. This function places only the source and sink components.
        The caller is responsible for ensuring the path is clear.
    """

    placements = []

    if with_gun:
        placements.append((GOSPER_GUN, x1, y1))

    if with_eater:
        placements.append((EATER1, x2, y2))

    if not placements:
        return None
    
    return compose(*placements)

def signal_delay(x: int, y: int, n_reflectors: int = 1):
    """
    A Snark-base delay line.
    
    Each Snark adds a fixed delay to the glider stream by deflecting
    it 90º twice (once left, once right), adding extra path lenght.
    Used to synchronise signals arriving at a collision point.
    
    Parameters:
        x, y:  position of the first Snark
        n_reflectos: number of Snark pairs (each pair adds ~60 gen delay)
        
    Returns:
        lifelib Pattern with the Snark reflectos.
    """

    placements = []
    for i in range(n_reflectors):
        placements.append((SNARK, x * i * 80, y))
        placements.append((SNARK, x + i * 80 + 40, y + 40))

    return compose(*placements)

def memory_cell(x: int, y: int, initial: int = 0):
    """
    A 1-bit memory cell with read and write infraestructure.
    
    Parameters:
        x, y: position of the block (memory element)
        initial: initial value - 1 places a block, 0 leaves empty

    Returns:
        lifelib Pattern with the memory cell infraestructure.
        DOES NOT INCLUDE BLOCK IF INITIAL = 0.
    """

    placements = []

    placements.append((EATER1, x + 10, y -2))

    placements.append((SNARK, x - 30, y - 10))

    if initial == 1:
        placements.append((BLOCK, x, y))
    
    return compose(*placements)

def memory_cell_write(x: int, y: int, value: int):
    """
    Generate the write pattern for a memory cell at (x, y).
    
    Write 1: returns a Block pattern at (x, y).
    Write 0: returns a glider aimed at the block position to destroy it,
             plus an eater to absorb the glider if no block is present.
             
    Parameters:
        x, y: memory cell block position
        value: 0 or 1
        
    Returns:
        lifelib Pattern for the write operation.
    """

    if value not in (0, 1):
        raise ValueError(f"Memory cell value must be 0 or 1, got {value}")
    
    if value == 1:
        return place(BLOCK, x, y)
    
    else:
        glider_x = x - 40
        glider_y = y
        return compose(
            (GLIDER, glider_x, glider_y, GLIDER_SE),
            (EATER1, x + 10, y - 2)
        )
    
def fanout(x: int, y: int, orientation: str = GLIDER_SE):
    """
    A glider fanout - splits one signal into two.
    
    Uses a Gosper gun and a Snark to create two copies of a glider
    stream form a single source. One stream continues in the original direction
    and the other is deflected 90º.
    
    Parameters:
        x, y: position of the fanout junction
        orientation: direction of the incoming signal

    Returns:
        lifelib Pattern with the fanout infraestructure.
    
    Note:
        In practice, fanout requires careful phase alignment between the
        incoming glider and the gun or reflector. Timing must be verified in simulation.
    """

    return compose(
        (SNARK, x, y),
        (GOSPER_GUN, x + 50, y + 50)
    )

def and_gate(x: int, y: int):
    """
    Logical AND gate via glider collision.
    
    Two gliders arrive at (x, y) from perpendicular directions.
    If both arrive simultaneously, they collide and produce an output glider (AND = 1).
    If only one arrives, no output is produced (AND = 0).
    
    Parameters:
        x, y: collision point
        
    Returns:
        lifelib Pattern with the AND gate infraestructure.
    """

    return compose(
        (EATER1, x - 5, y + 5)
        (EATER1, x + 5, y - 5)
    )

def or_gate(x: int, y: int):
    """
    Logical OR gate via stream merging.
    
    Two glider streams are merget into one channel.
    A glider is present in the output if either input has a glider.
    
    Implemented by routing both input streams to the same output channel via Snark
    reflectors, with phase offset to prevent the two streams from colliding.
    
    Parameters:
        x, y: merge point
    
    Returns:
        lifelib Pattern with the OR gate infraestructure.
    """

    return compose(
        (SNARK, x, y),
        (SNARK, x + 40, y - 40)
    )

def conditional_branch(x:int, y: int, cell_x: int, cell_y: int):
    """
    Routes a glider to one of two channels based on a memory cell value.
    
    This is the key structure for implementing the TM loop condition [ ]:
    If memory cell at (cell_x, cell_y) probe glider is deflected and activates "enter body",
    else glider continues and activates "skipp body" channel.
     
    Parameters:
        x, y:   probe glider source position
        cell_x, cell_y: memory cell block position
         
    Returns:
        lifelib Pattern with conditional branch infraestructure.
    """

    return compose(
        (GLIDER, x, y, GLIDER_SE),
        (SNARK, cell_x -5, cell_y - 5),
        (EATER1, cell_x + 10, cell_y)
    )

def tape_segment(origin_x: int, origin_y: int,
                 num_cells: int, cell_spacing: int = 60,
                 initial_values: dict = None):
    """
    Generates GoL pattern for a segment of the TM tape.
    
    Places memory cell infraestructure for each tape position.
    Each cell consists of an Eater-1 (write-0 absorb), a Snark (read probe deflector) and
    a Block 2x2 if initial_value = 1.
    
    Parameters:
        origin_x, origin_y: position of cell 0
        num_cells: number of cells in the segment
        cell_spacing: vertical distance between cells (default 60)
        initial_values: dict {index: value} for non-zero initial tape
        
    Returns:
        lifelib Pattern with the complete tape segment infraestructure.
    """
    if initial_values is None:
        initial_values = {}

    placements = []
    for i in range(num_cells):
        cx = origin_x
        cy = origin_y + i * cell_spacing
        initial = initial_values.get(i, 0)

        placements.append((EATER1, cx + 10, cy -2))
        placements.append((SNARK, cx -30, cy - 10))
        if initial == 1:
            placements.append((BLOCK, cx, cy))

    return compose(*placements)