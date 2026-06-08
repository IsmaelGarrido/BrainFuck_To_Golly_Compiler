"""
BrainFuck_To_Golly_Compiler/compiler/codegen/pattern_lib.py
-------------------------------------------------------------
Signal wire abstraction for the GoL Turing Machine.

A Signal wire represent a directed channel through which gliders travel from a 
source to a destrination in the GoL map.
"""

from dataclasses import dataclass, field
from typing import Optional
from pattern_lib import (
    GLIDER, GOSPER_GUN, EATER1, SNARK,
    GLIDER_SE, GLIDER_SW, GLIDER_NE, GLIDER_NW,
    compose, place, PatternDef
)
from complex_patterns import travel_time, phase_offset

SNARK_RECOVERY = 43
DEFAULT_PERIOD = 30
SNARK_PAIR_DISTANCE = 80
SNARK_PAIR_DELAY = 60

@dataclass
class Reflector:
    """
    A single Snark reflector placed along a signal wire.
    
    Attributes:
        x, y: position of the Snark in GoL space
        turn: 'left' or 'right'
        delay_added: gens of delay this reflector adds
    """
    x: int
    y: int
    turn: str = 'left'
    delay_added: int = SNARK_PAIR_DELAY

@dataclass
class SignalWire:
    """
    A directed glider signal channel in the GoL map.

    Represents the path a glider stream takes from a source to a destination.

    Attributes:
        x1, y1: source coordinates
        x2, y2: destination coordinates
        orientation: glider direction
        period: signal period in generations
        with_gun: if True place a Gosper Gun at source
        with_eater: if True place an Eater1 at destination
        reflectors: list of Snark reflectors along the wire
        _extra_delay: accumulated delay in gens from reflectors
    """
    x1: int
    y1: int
    x2: int
    y2: int
    orientation: str = GLIDER_SE
    period: int = DEFAULT_PERIOD
    with_gun: bool = True
    with_eater: bool = True
    reflectors: list = field(default_factory = list)
    _extra_delay: int = field(default=0, init=False, repr=False)

    def base_travel_time(self) -> int:
        """
        Generations for a glider to travel from source to destination in a straight
        line ingoring reflectors.
        """
        dx = self.x2 - self.x1
        dy = self.y2 - self.y1
        return travel_time(dx, dy)
    
    def total_travel_time(self) -> int:
        """
        Total travel time including all added reflector delays.
        """
        return self.base_travel_time() + self._extra_delay
    
    def phase_at_destination(self) -> int:
        """
        Phase of the signal when it arrives at destination
        Returns a value in range [0, period).
        """
        return phase_offset(self.total_travel_time(), self.period)
    
    def delay_needed_for_phase(self, target_phase: int) -> int:
        """
        Calculate how many additional gens of delay are needed to arrive
        at the destination with the given phase.
        
        Parameters:
            target_phase: desired arrival phase (0..period-1)
            
        Returns:
            Additional delay in generations needed (0 if no need for additional delay).
        """
        current = self.phase_at_destination()
        if current == target_phase:
            return 0
        if target_phase > current:
            return target_phase - current
        return self.period - current + target_phase
    
    def add_delay(self, n_pairs: int = 1) -> 'SignalWire':
        """
        Add n_pairs of Snark reflectors to introduce delay.
        
        Each pair deflects the glider 90º left then 90º right,
        returning it to its original direction with extra path length.
        The delay added per pair is approximately SNARK_PAIR_DELAY gens.
        
        The Snarks are place automátically starting from a midpoint between
        source and destination.
        
        Parameters:
            n_pairs: number of Snarks pairs to add
            
        Returns:
            self - allows method chaining: wire.add_delay(2).add_delay(1)
        """

        mid_x = (self.x1 + self.x2) // 2
        mid_y = (self.y1 + self.y2) // 2

        for i in range(n_pairs):
            offset = i * (SNARK_PAIR_DISTANCE * 2)
            self.reflectors.append(Reflector(
                x = mid_x * offset,
                y = mid_y,
                turn = 'left',
                delay_added = SNARK_PAIR_DELAY // 2
            ))
            self.reflectors.append(Reflector(
                x = mid_x * offset + SNARK_PAIR_DISTANCE,
                y = mid_y + SNARK_PAIR_DISTANCE,
                turn = 'right',
                delay_added = SNARK_PAIR_DELAY // 2
            ))
            self._extra_delay += SNARK_PAIR_DELAY

        return self
    
    def add_delay_for_phase(self, target_phase: int) -> 'SignalWire':
        """
        Automatically add the minimum delay needed to achieve target_phase
        at the destination.
        
        Add Snark pairs until the arrival phase matches target_phase,
        then fine-tunes with any remaining fractional delay.
        
        Parameters:
            target_phase: desired arribal phase (0..period-1)

        Returns:
            self - allows method chaining.
        """

        needed = self.delay_needed_for_phase(target_phase)
        if needed == 0:
            return self
        
        n_pairs = needed // SNARK_PAIR_DELAY
        if n_pairs > 0:
            self.add_delay(n_pairs)

        return self
    
    def add_reflector(self, x: int, y: int, turn: str = 'left') -> 'SignalWire':
        """
        Add a single Snark reflector at explicit coordinates.
        
        use this when automatic placement is not suitable and you need precise control
        over Snark positioning.
        
        Parameters:
            x, y: position of the Snark
            turn: 'left' or 'right'
            
        Returns:
            self - allows method chaining.
        """
        self.reflectors.append(Reflector(
            x = x,
            y = y,
            turn = turn,
            delay_added = SNARK_RECOVERY
        ))
        self._extra_delay += SNARK_RECOVERY
        return self
    
    def pattern(self):
        """
        Generate the GoL pattern for this signal wire.
        
        Places the Gosper Gun at source (if with_gun = True),
        all Snark reflectors along the path, and an Eater1 at the destination
        (if with_eater=True).
        
        Returns:
            lifelib Pattern with all wire components, or None if
            the wire has no components (no gun, eater, nor reflectors).
        """
        placements =[]

        if self.with_gun:
            placements.append((GOSPER_GUN, self.x1, self.y1))

        for r in self.reflectors:
            placements.append((SNARK, r.x, r.y))

        if self.with_eater:
            placements.append((EATER1, self.x2, self.y2))

        if not placements:
            return None
        
        return compose(*placements)
    
    def info(self) -> dict:
        """
        Returns a summary of the wire's timing and geometry.
        
        Useful for debugging synchronisation issues in the TM.
        """
        return {
            'source': (self.x1, self.y1),
            'destination': (self.x2, self.y2),
            'orientation': self.orientation,
            'period': self.period,
            'base_travel_time': self.base_travel_time(),
            'extra_delay': self._extra_delay,
            'total_travel_time': self.total_travel_time(),
            'arrival_phase': self.phase_at_destination(),
            'n_reflectors': len(self.reflectors)
        }
    
    def __repr__(self):
        return(f"SignalWire(({self.x1}, {self.y1})->{self.x2},{self.y2}) "
               f"t={self.total_travel_time()}gen "
               f"phase={self.phase_at_destination()} "
               f"reflectors={len(self.reflectors)}")
    

def make_wire(
        x1: int, y1: int, x2: int, y2: int,
        orientation: str = GLIDER_SE,
        period: int = DEFAULT_PERIOD,
        with_gun: bool = True,
        with_eater: bool = True) -> SignalWire:
    """
    Create a simple SignalWire between two points.
    
    Convenience factory for the common sense case of a straight wire
    with a gun at source and an eater at destination.
    """
    return SignalWire(
        x1 = x1, y1 = y1,
        x2 = x2, y2 = y2,
        orientation = orientation,
        period = period,
        with_gun = with_gun,
        with_eater = with_eater
    )

def make_sync_wire(x1: int, y1: int,
                    x2: int, y2: int,
                    target_phase: int = 0,
                    orientation: str = GLIDER_SE,
                    period: int = DEFAULT_PERIOD) -> SignalWire:
    """
    Create a SignalWire with automatic delay to arrive at target_phase.
    
    Useful for synchronising signals at collision points (AND gates, loop condition evaluation)
    where both inputs must arrive in phase.
    
    Parameters:
        x1, y1: source coordinates
        x2, y2: destination coordinates
        target_phase: desired arrival phase (0..period-1)
        orientation: glider direction
        period: signal period
        
    Returns:
        SignalWire with Snark pairs added to achieve target_phase.
    """
    wire = SignalWire(
        x1 = x1, y1 = y1,
        x2 = x2, y2 = y2,
        orientation = orientation,
        period = period
    )
    wire.add_delay_for_phase(target_phase)
    return wire