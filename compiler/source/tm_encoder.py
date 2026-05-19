"""
BrainFuck_To_Golly_Compiler/compiler/source/mt_encoder.py
----------------------------------------------------
MT Encoder (intermediate representation).

Translates BF AST into Turing Machine transition table.
"""

from dataclasses import dataclass, field
from parser import Instruction, Loop, AST

ALPHABET_SIZE   = 256
ALPHABET        = tuple(range(ALPHABET_SIZE))

@dataclass
class Transition:
    """
    A Single MT Transition Rule (quintuple).
    
    Represents on rule of the transition function δ:
        δ(state, read) = (new_state, write, direction)
        
    Attributes:
        state:      current state
        read:       symbol under the head(0..255)
        new_state:  state to transition to
        write:      symbol written to the tape (0..255)
        direction:  head movement - 'L', 'R' or 'N' (stationary)
        is_output:  True if this transition is a '.' instruction
    """

    state:      int
    read:       int
    new_state:  int
    write:      int
    direction:  int
    is_output:  bool = False
    
    def __repr__(self):
        out = " [OUT]" if self.is_output else ""
        return (f"({self.state}, {self.read:3d}) "
                f"-> ({self.new_state}, {self.write:3d}, {self.direction}){out}")


@dataclass
class TMProgram:
    """
    Result of encoding a BF programm as a Turing Machine.
    
    Attributes:
        transitions:    complete transition table as a list of quintuples
        initial_state:  state where execution begins (always 0)
        accept_state:   state that signals successful termination
        num_states:     total number of states generated
        alphabet_size:  number of symbols in the alphabet (256 for full BF)
    """    
    transitions:    list[Transition]
    initial_state:  int
    accept_state:   int
    num_states:     int
    alphabet_size:  int = ALPHABET_SIZE

    def transitions_from(self, state: int) -> list[Transition]:
        """Returns all transitions departing from a given state."""
        return [t for t in self.transitions if t.state == state]
    
    def transition_for(self, state: int, symbol: int) -> 'Transition | None':
        """Returns the unique transition for (state, symbol), or None."""
        for t in self.transitions:
            if t.state == state and t.read == symbol:
                return t
        
        return None
    
    def is__deterministic(self) -> bool:
        """
        Verifies if TM is deterministic:
        at most one transtiion per (state, symbol) pair.
        """
        seen = set()
        for t in self.transitions:
            key = (t.state, t.read)
            if key in seen:
                return False
            
            seen.add(key)
        
        return True
    
    def output_transitions(self) -> list[Transition]:
        """Returns all transitions flagged as output (from '.' instructions)."""
        return [t for t in self.transitios if t.is_output]
    
    @property
    def Q(self) -> set[int]:
        """
        Q - complete set of states.
        
        Derived from the transition table: any state appearing as source
        or destination of a transition is a member of Q.
        """
        result = set()
        for t in self.transitions:
            result.add(t.state)
            result.add(t.new_state)
        return result
    
    @property
    def tape_alphabet(self) -> set[int]:
        """
        r - tape alphabet.
        
        All symbols appearing as read or write values in the table.
        In a BF-derived TM this is a subset of {0..255}.
        """
        result = set()
        for t in self.transitions:
            result.add(t.read)
            result.add(t.write)
        
        return result
    
    @property 
    def input_alphabet(self) -> set[int]:
        """
        Σ — input alphabet.
        
        Symbols appearing as read values in transitions from the initial state.
        In practice equals tape_alphabet for BF programs.
        """
        return {t.read for t in self.transitions_from(self.initial_state)}
    
    def as_formal_tuple(self) -> dict:
        """
        Returns a dictionary representing the formal 7-tuple components.
        
        Returns:
            dict with keys: Q, Sigma, Gmma, q0, q_accept, num_transitions
        """
        return {
            'Q':                self.Q,
            'Sigma':            self.input_alphabet,
            'Gamma':            self.tape_alphabet,
            'q0':               self.initial_state,
            'q_accept':         self.accept_state,
            'num_transitions':  len(self.transitions)
        }

class EncoderError(Exception):
    """Error during TM encoding"""
    pass

def encode(ast: AST) -> TMProgram:
    """
    Translates a BF AST into an TM transition table.
    
    Parameters:
        ast: well-formed AST produced by parser
        
    Returns:
        TMProgram with the complete transition table over alphabet{0..255},
        initial state, accept state and total state count.
    
    Raises:
        EncoderError: if the AST contains unsupported instructions (e.g. ',')
    """
    transitions: list[Transition] = []
    counter = [0]

    def new_state()-> int:
        """Allocates a new unique state identifier."""
        s = counter[0]
        counter[0] += 1
        return s
    
    def encode_nodes(nodes: list, entry: int) -> int:
        """
        Encodes a list of AST nodes starting from entry state.
        
        Returns the last state generated so the caller can connect it
        to the accept state or an outer loop re-entry point.
        """

        current = entry
        
        for node in nodes:
                if isinstance(node, Instruction):
                        match node.op:
                            case '>' | '<':
                                direction = 'R' if node.op == '>' else 'L'
                                next_s = new_state()
                                for sym in ALPHABET:
                                    transitions.append(Transition(
                                        state=current, read=sym,
                                        new_state=next_s, write=sym,
                                        direction=direction
                                    ))
                                current = next_s
                            
                            case '+':
                                next_s = new_state()
                                for sym in ALPHABET:
                                    transitions.append(Transition(
                                        state=current, read=sym,
                                        new_state=next_s,
                                        write=(sym + 1) % ALPHABET_SIZE,
                                        direction='N'
                                    ))
                                current = next_s

                            case '-':
                                next_s = new_state()
                                for sym in ALPHABET:
                                    transitions.append(Transition(
                                        state=current, read=sym,
                                        new_state=next_s,
                                        write=(sym - 1) % ALPHABET_SIZE,
                                        direction='N'
                                    ))
                                current = next_s
                            
                            case '.':
                                next_s = new_state()
                                for sym in ALPHABET:
                                    transitions.append(Transition(
                                        state=current, read=sym,
                                        new_state=next_s, write=sym,
                                        direction='N', is_output=True
                                    ))
                                current = next_s
                            
                            case _:
                                raise EncoderError(
                                        f"Unrecognised instructions: '{node.op}"
                                )
                        
                elif isinstance(node, Loop):
                    loop_entry = current
                    body_entry = new_state()
                    loop_exit = new_state()

                transitions.append(Transition(
                    state=loop_entry, read=0,
                    new_state=loop_exit, write=0, direction='N'
                ))
                for sym in ALPHABET[1:]:
                    transitions.append(Transition(
                        state=loop_entry, read=sym,
                        new_state=body_entry, write=sym, direction='N'
                    ))
                    
                    if node.body:
                        body_last = encode_nodes(node.body, body_entry)
                    else:
                        body__last = body_entry

                    for sym in ALPHABET:
                        transitions.append(Transition(
                            state=body_last, read=sym,
                            new_state=loop_entry, write=sym, direction='N'
                        ))

                    current = loop_exit

        return current

    initial = new_state()
    last = encode_nodes(ast, initial)

    accept = new_state()
    for sym in ALPHABET:
        transitions.append(Transition(
            state=last, read=sym,
            new_state=accept, write=sym, direction='N'
        ))

    return TMProgram(
        transitions= transitions,
        initial_state= initial,
        accept_state= accept;
        num_states= counter[0],
        alphabet_size= ALPHABET_SIZE
    )

def encode_source(source: str) -> TMProgram:
    """
    Encodes BF source code directly (lexer + parser + encode).
    """
    from lexer import tokenize
    from parser import parse
    return encode(parse(tokenize(source)))

