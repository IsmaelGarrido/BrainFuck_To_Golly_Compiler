"""
Brainfuck_To_Golly_Compiler/compiler/codegen/tape.py
----------------------------------
Tape structure for the GoL Turing Machine.

Defines the spatial layout of the binary tape in the GoL universe, 
provide SinalWire objects for read and write operations on tape cells.
"""

from dataclasses import dataclass, field
from typing import Optional
from pattern_lib import(
    BLOCK, EATER1, GLIDER, SNARK,
    GLIDER_SE, GLIDER_NE, GLIDER_SW, GLIDER_NW,
    compose, place
)

from complex_patterns import tape_segment
from signal_wire import SignalWire, make_wire, SNARK_RECOVERY, DEFAULT_PERIOD

CELL_SPACING = 60
TAPE_ORIGIN_X = 200
TAPE_ORIGIN_Y = 200
MIN_TAPE_CELLS = 10

READ_PROBE_OFFSET = 40

WRITE_GLIDER_OFFSET = 40

@dataclass
class TapeCell:
    """
    Represents one cell of the binary tape in the GoL universe.

    Attributes:
        index: position on the tape(0 = first cell)
        x: X coordinate of the block position in GoL
        y: Y coordinate of the block position in GoL
        initial: initial value (0 or 1). BF programs start with black tape.
    """
    index: int
    x: int
    y: int
    initial: int = 0

    def __post_init__(self):
        if self.initial not in (0,1):
            raise ValueError(
                f"Tapecell initial value must be 0 or 1, got {self.initial}."
            )    

    @property
    def block_position(self) -> tuple[int, int]:
        """(x, y) where Block 2x2 is placed when this cell = 1."""
        return (self.x, self.y)

    @property
    def read_probe_origin(self) -> tuple[int, int]:
        """
        (x, y) where a read probe glider start.
        Offset to the left of the block to allow travel distance.
        """
        return (self.x - READ_PROBE_OFFSET, self.y)

    @property
    def write_origin(self) -> tuple[int, int]:
        """
        (x, y) where write-0 glider starts.
        Aimed rightward toward the block position.
        """
        return (self.x - WRITE_GLIDER_OFFSET, self.y)

    def __repr__(self):
        return (f"TapeCell(index={self.index},"
                f"pos=({self.x}, {self.y}), init={self.initial}")

@dataclass
class Tape:
    """
    The complete binary tape of the Turing Machine in GoL space.
    
    Manages the spatial layout of the tape cells and provides SignalWire
    objects for read and write operations.
    
    Attributes:
        num_cells:      number of cells pre-allocated
        origin_x:       X coordinate of the tape column
        origin_y:       Y coordinate of cell 0
        cell_spacing:   vertical distance between cells
        cells:          list of TapeCell objects
    """
    num_cells: int = MIN_TAPE_CELLS
    origin_x: int = TAPE_ORIGIN_X
    origin_y: int = TAPE_ORIGIN_Y
    cell_spacing: int = CELL_SPACING
    cells: list = field(default_factory=list)

    def __post_init__(self):
        if not self.cells:
            self._allocate_cells(self.num_cells)

    def _allocate_cells(self, up_to: int) -> None:
        """Allocate cells up to the given count."""
        start = len(self.cells)
        for i in range(start, up_to):
            self.cells.append(TapeCell(
                index = i,
                x = self.origin_x,
                y = self.origin_y + i * self.cell_spacing
            ))

    def cell(self, index: int) -> TapeCell:
        """
        Returns the TapeCell at the given index.
        Extend the tape automatically if index is beyond current size.
        Models the logically infinite tape of the Turing Machine.
        """
        if index >= len(self.cells):
            self._allocate_cells(index+1)
        return self.cells[index]
    
    def position_of(self, index: int) -> tuple[int, int]:
        """Returns the (x, y) GoL coordinates of tape cell at index."""
        return self.cell(index).block_position
    
    def y_of(self, index: int) -> int:
        """Return the Y coordinate of tape cell at index."""
        return self.origin_y + index * self.cell_spacing
    
    def index_of_y(self, y: int) -> Optional[int]:
        """
        Returns the tape index for a Y coordinate, or None if not aligned.
        """
        offset = y - self.origin_y
        if offset < 0 or offset % self.cell_spacing != 0:
            return None
        return offset // self.cell_spacing
    
    def initial_pattern(self, initial_values: dict = None):
        """
        Generate the GoL pattern for the initial tape configuration.
        
        Uses complex_patterns.tape_segment() to place the full
        infraestructure (Eaters, Snarks, Blocks) for all cells.
        
        Parameters:
            initial_values: dict {index: value} for non-zero initial cells.
                            None or empty dict = blank tape (all zeros).

        Returns:
            lifelib Pattern with the complete tape infraestructure,
            or None if tape is blank and has no infraestructure.
        """
        if initial_values is None:
            initial_values = {}

        return tape_segment(
            origin_x = self.origin_x,
            origin_y = self.origin_y,
            num_cells = len(self.cells),
            cell_spacing = self.cell_spacing,
            initial_values = initial_values
        )
    
    def blank_tape_pattern(self):
        """
        Return the GoL pattern for a blank tape (all cells = 0).
        Infraestructure (Eaters, Snarks) is still placed.
        """
        return self.initial_pattern({})
    
    def read_wire(self, index: int,
                  period: int = DEFAULT_PERIOD) -> SignalWire:
        """
        Return a SignalWire for a non-destructive read of cell at index.
        
        The probe glider travels from read_probe_origin toward the block
        position. If the block is present (cell=1), it is deflected by the
        Snark in the memory cell infraestructure -> signal A.
        If absent (cell = 0), it continues right -> singal B.

        Parameters:
            index: tape cell index to read
            period: signal period (default 30)
        
        Returns:
            SignalWire from probe origin to block position.    
        """
        cell = self.cell(index)
        px, py = cell.read_probe_origin
        bx, by = cell.block_position

        return make_wire(
            x1 = px,
            y1 = py,
            x2 = bx,
            y2 = by,
            orientation = GLIDER_SE,
            period = period,
            with_gun = True,
            with_eater = False
        )
    
    def write_wire(self, index: int, value: int,
                   period: int = DEFAULT_PERIOD) -> SignalWire:
        """
        Returns a SignalWire for writing a value to cell at index.
        
        Write 1: the wire carries a glider that triggers block placement.
        Write 0: the wire carries a glider that destroys the block
        
        Parameters:
            index: tape cell index to write
            value: 0 or 1
            period: signal period

        Returns:
            SignalWire from write origin to block position.

        Raises:
            ValueError: if value is not 0 or 1
        """
        if value not in (0, 1):
            raise ValueError(f"Tape value must be 0 or 1, got {value}")
        
        cell = self.cell(index)
        wx, wy = cell.write_origin
        bx, by = cell.block_position

        return make_wire(
            x1 = wx,
            y1 = wy,
            x2 = bx,
            y2 = by,
            orientation = GLIDER_SE,
            period = period,
            with_gun = True,
            with_eater = (value == 0)
        )
    
    def head_position_pattern(self, index: int):
        """
        Returns a GoL pattern marking the current head position.
        
        Places a Blinker nexxt to the active cell as a visual indicator.
        Used for debugging in Golly - not part of the computation.
        
        Parameters:
            index: active tape cell index
            
        Returns:
            lifelib Pattern with the head position marker.
        """
        from pattern_lib import BLINKER
        cell = self.cell(index)
        return place(BLINKER, cell.x + 5, cell.y)
    
    def __len__(self) -> int:
        return len(self.cells)
    
    def __repr__(self):
        return (f"Tape(cells={len(self.cells)},"
                f"origin=({self.origin_x},{self.origin_y}),"
                f"spacing={self.cell_spacing}")
    
def make_tape(num_cells: int = MIN_TAPE_CELLS,
              origin_x: int = TAPE_ORIGIN_X,
              origin_y: int = TAPE_ORIGIN_Y) -> Tape:
    """
    Crate a Tape with the given parameters.
    
    Parameters:
        num_cells: number of cells to pre-allocate
        origin_x: X coordinate of the tape column
        origin_y: Y coordinate of cell 0
        
    Returns:
        Tape instance with num_cells blank cells.
    """
    return Tape(
        num_cells=num_cells,
        origin_x=origin_x,
        origin_y=origin_y,
        cell_spacing=CELL_SPACING
    )