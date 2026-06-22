"""
compiler/semantic/tm_encoder.py
-------------------------------
Phase 2 of the compiler: Turing-machine encoding and Simkin export.
"""

from dataclasses import dataclass, field
from parser import Instruction, Loop, AST

ALPHABET_SIZE = 2
ALPHABET      = tuple(range(ALPHABET_SIZE))



@dataclass
class Transition:
    """
    A single MT transition rule (quintuple).

    Represents one rule of the transition function:
        transition(state, read) = (new_state, write, direction)

    Attributes:
        state:     current state
        read:      symbol under the head (0..255)
        new_state: state to transition to
        write:     symbol written to the tape (0..255)
        direction: head movement — 'L', 'R' or 'N' (stationary)
        is_output: True if this transition corresponds to a '.' instruction
    """
    state:     int
    read:      int
    new_state: int
    write:     int
    direction: str
    is_output: bool = False

    def __repr__(self):
        out = " [OUT]" if self.is_output else ""
        return (f"({self.state}, {self.read:3d}) "
                f"→ ({self.new_state}, {self.write:3d}, {self.direction}){out}")


@dataclass
class MTProgram:
    """
    Result of encoding a BF program as a Turing Machine.

    Attributes:
        transitions:    complete transition table as a list of quintuples
        initial_state:  state where execution begins (always 0)
        accept_state:   state that signals successful termination
        num_states:     total number of states generated
        alphabet_size:  number of symbols in the alphabet (2 for the
                        Simkin pipeline)
    """
    transitions:   list[Transition]
    initial_state: int
    accept_state:  int
    num_states:    int
    alphabet_size: int = ALPHABET_SIZE

    def transitions_from(self, state: int) -> list[Transition]:
        return [t for t in self.transitions if t.state == state]

    def transition_for(self, state: int, symbol: int) -> 'Transition | None':
        for t in self.transitions:
            if t.state == state and t.read == symbol:
                return t
        return None

    def is_deterministic(self) -> bool:
        seen = set()
        for t in self.transitions:
            key = (t.state, t.read)
            if key in seen:
                return False
            seen.add(key)
        return True

    def output_transitions(self) -> list[Transition]:
        return [t for t in self.transitions if t.is_output]

    @property
    def Q(self) -> set[int]:
        """
        complete set of states.

        Derived from the transition table: any state appearing as source
        or destination of a transition is a member of Q.
        Equivalent to the explicit Q in the formal 7-tuple definition.
        """
        result = set()
        for t in self.transitions:
            result.add(t.state)
            result.add(t.new_state)
        return result

    @property
    def tape_alphabet(self) -> set[int]:
        """
        tape alphabet.

        All symbols appearing as read or write values in the table.
        For the binary Simkin pipeline this is {0, 1}.

        Note: Γ ⊇ Σ (tape alphabet contains the input alphabet).
        """
        result = set()
        for t in self.transitions:
            result.add(t.read)
            result.add(t.write)
        return result

    @property
    def input_alphabet(self) -> set[int]:
        """
        input alphabet.

        Symbols appearing as read values in transitions from the
        initial state. In practice equals tape_alphabet for BF programs
        since any cell value can be under the head at any point.
        """
        return {t.read for t in self.transitions_from(self.initial_state)}

    def as_formal_tuple(self) -> dict:
        return {
            'Q':               self.Q,
            'Sigma':           self.input_alphabet,
            'Gamma':           self.tape_alphabet,
            'q0':              self.initial_state,
            'q_accept':        self.accept_state,
            'num_transitions': len(self.transitions),
        }


# ── ERRORS ────────────────────────────────────────────────────────────────────

class EncoderError(Exception):
    """Error during MT encoding."""
    pass


# ── ENCODER ───────────────────────────────────────────────────────────────────

def encode(ast: AST, alphabet_size: int = ALPHABET_SIZE) -> MTProgram:
    """
    Translates a BF AST into an MT transition table.

    Parameters:
        ast:           well-formed AST produced by the parser
        alphabet_size: number of tape symbols (default 2, binary). The
                       Simkin export requires 2.

    Returns:
        MTProgram with the complete transition table over the given alphabet,
        initial state, accept state and total state count.

    Raises:
        EncoderError: if the AST contains unsupported instructions (e.g. ',')
    """
    alphabet     = tuple(range(alphabet_size))
    transitions: list[Transition] = []
    counter      = [0]

    def new_state() -> int:
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
                        for sym in alphabet:
                            transitions.append(Transition(
                                state=current, read=sym,
                                new_state=next_s, write=sym,
                                direction=direction
                            ))
                        current = next_s

                    case '+':
                        next_s = new_state()
                        for sym in alphabet:
                            transitions.append(Transition(
                                state=current, read=sym,
                                new_state=next_s,
                                write=(sym + 1) % alphabet_size,
                                direction='N'
                            ))
                        current = next_s

                    case '-':
                        next_s = new_state()
                        for sym in alphabet:
                            transitions.append(Transition(
                                state=current, read=sym,
                                new_state=next_s,
                                write=(sym - 1) % alphabet_size,
                                direction='N'
                            ))
                        current = next_s

                    case '.':
                        next_s = new_state()
                        for sym in alphabet:
                            transitions.append(Transition(
                                state=current, read=sym,
                                new_state=next_s, write=sym,
                                direction='N', is_output=True
                            ))
                        current = next_s

                    case ',':
                        raise EncoderError(
                            "Instruction ',' (input) is not supported in v1. "
                            "Documented limitation."
                        )

                    case _:
                        raise EncoderError(
                            f"Unrecognised instruction: '{node.op}'"
                        )

            elif isinstance(node, Loop):
                loop_entry = current
                body_entry = new_state()
                loop_exit  = new_state()

                transitions.append(Transition(
                    state=loop_entry, read=0,
                    new_state=loop_exit, write=0, direction='N'
                ))
                for sym in alphabet[1:]:
                    transitions.append(Transition(
                        state=loop_entry, read=sym,
                        new_state=body_entry, write=sym, direction='N'
                    ))

                if node.body:
                    body_last = encode_nodes(node.body, body_entry)
                else:
                    body_last = body_entry

                for sym in alphabet:
                    transitions.append(Transition(
                        state=body_last, read=sym,
                        new_state=loop_entry, write=sym, direction='N'
                    ))

                current = loop_exit

        return current

    initial = new_state()
    last    = encode_nodes(ast, initial)

    accept  = new_state()
    for sym in alphabet:
        transitions.append(Transition(
            state=last, read=sym,
            new_state=accept, write=sym, direction='N'
        ))

    return MTProgram(
        transitions   = transitions,
        initial_state = initial,
        accept_state  = accept,
        num_states    = counter[0],
        alphabet_size = alphabet_size
    )

def eliminate_stationary(program: MTProgram) -> MTProgram:
    """
    Return an equivalent MTProgram with no stationary ('N') head moves,
    using only 'L' and 'R'.

    Parameters:
        program: an MTProgram that may contain 'N' transitions.

    Returns:
        An equivalent MTProgram whose transitions use only 'L' and 'R'.
        If the input already has no 'N' transitions, an equivalent program
        is returned unchanged in behaviour.
    """
    alphabet = list(range(program.alphabet_size))

    next_state = [program.num_states]

    def new_state() -> int:
        s = next_state[0]
        next_state[0] += 1
        return s

    new_transitions: list[Transition] = []

    for t in program.transitions:
        if t.direction != 'N':
            new_transitions.append(t)
            continue

        aux = new_state()

        new_transitions.append(Transition(
            state=t.state, read=t.read,
            new_state=aux, write=t.write, direction='R',
            is_output=t.is_output,
        ))

        for sym in alphabet:
            new_transitions.append(Transition(
                state=aux, read=sym,
                new_state=t.new_state, write=sym, direction='L',
            ))

    return MTProgram(
        transitions   = new_transitions,
        initial_state = program.initial_state,
        accept_state  = program.accept_state,
        num_states    = next_state[0],
        alphabet_size = program.alphabet_size,
    )

def to_simkin_rule(program: MTProgram,
                   input_tape: list = None,
                   head_start: int = 0) -> str:
    """
    Serialise an MTProgram as a Michael Simkin "turing rule" string, ready
    to paste into his Golly Turing-machine simulator.

    Simkin's format (one machine per clipboard string):

        <line 1: input tape, space-separated symbols>
        <line 2: input-tape head start location>
        <one line per (symbol, state) combination:>
            <tape> <head> <new_tape> <new_head> <l/r>

    Parameters:
        program:    a stationary-free MTProgram.
        input_tape: initial tape contents as a list of ints. Defaults to a
                    single 0 cell. Symbols must be < alphabet_size.
        head_start: head start location on the input tape (default 0).

    Returns:
        A string in Simkin's turing-rule format.
    """
    if program.initial_state != 0:
        raise ValueError(
            f"Simkin requires the start state to be 0, but this program "
            f"starts at {program.initial_state}."
        )

    if any(t.direction == 'N' for t in program.transitions):
        raise ValueError(
            "Program still contains stationary ('N') moves; call "
            "eliminate_stationary() before exporting to Simkin's format."
        )

    if input_tape is None:
        input_tape = [0]
    for sym in input_tape:
        if not (0 <= sym < program.alphabet_size):
            raise ValueError(
                f"tape symbol {sym} outside alphabet "
                f"0..{program.alphabet_size - 1}"
            )

    accept         = program.accept_state
    accept_partner = program.num_states

    states   = range(program.num_states + 1)
    symbols  = range(program.alphabet_size)

    table = {(t.state, t.read): t for t in program.transitions}

    lines = []
    lines.append(" ".join(str(s) for s in input_tape))
    lines.append(str(head_start))

    for state in states:
        for sym in symbols:
            if state == accept:
                new_state = accept_partner
                write     = sym
                direction = 'r'
            elif state == accept_partner:
                new_state = accept
                write     = sym
                direction = 'l'
            else:
                t = table.get((state, sym))
                if t is None:
                    new_state = state
                    write     = sym
                    direction = 'r'
                else:
                    new_state = t.new_state
                    write     = t.write
                    direction = t.direction.lower()
            lines.append(f"{sym} {state} {write} {new_state} {direction}")

    return "\n".join(lines)

def compile_to_simkin(source: str,
                      alphabet_size: int = 2,
                      input_tape: list = None,
                      head_start: int = 0) -> str:
    """
    End-to-end: BF source → stationary-free MT → Simkin turing-rule string.

    Parameters:
        source:        BF source code.
        alphabet_size: tape alphabet size; must be 2.
        input_tape:    initial tape (default: zeros sized to the program).
        head_start:    head start location (default 0, the origin).

    Returns:
        A Simkin turing-rule string.

    Raises:
        UnilateralTapeError: if the program may move left of the origin.
        ValueError:          if alphabet_size != 2.
    """
    if alphabet_size != 2:
        raise ValueError(
            f"the Simkin export is binary only (alphabet_size must be 2, got {alphabet_size})."
        )

    check_unilateral_safe(source)

    if input_tape is None:
        input_tape = [0] * required_tape_length(source)

    from lexer import tokenize
    from parser import parse
    ast = strip_output_nodes(parse(tokenize(source)))
    mt = encode(ast, alphabet_size=alphabet_size)
    mt = eliminate_stationary(mt)
    return to_simkin_rule(mt, input_tape=input_tape, head_start=head_start)

def strip_output_nodes(ast):
    """
    Return a copy of the AST with every '.' (output) instruction removed,
    recursively, including inside loops.

    Parameters:
        ast: an AST (list of Instruction | Loop) from the parser.

    Returns:
        A new AST with all Instruction('.') nodes removed at every depth.
    """
    from parser import Instruction, Loop
    result = []
    for node in ast:
        if isinstance(node, Instruction):
            if node.op == '.':
                continue                      
            result.append(node)
        elif isinstance(node, Loop):
            result.append(Loop(body=strip_output_nodes(node.body)))
        else:
            result.append(node)
    return result


class UnilateralTapeError(Exception):
    """
    The BF program may move the pointer left of the origin (cell 0), which
    cannot be placed on Simkin's one-sided tape.
    """


def analyze_pointer(source: str) -> dict:
    """
    Static pointer analysis for the Simkin export.

    Simkin's tape is one-sided: it extends rightward from cell 0 and there is
    nothing left of the origin.
    Returns a dict with:
        crosses_origin   (bool): a concrete '<' takes the pointer below 0.
        min_offset       (int) : leftmost pointer position reached (<= 0).
        max_right        (int) : rightmost pointer position reached (>= 0).
        origin_decidable (bool): False if a loop has net leftward drift, so
                                 origin-crossing cannot be ruled out statically.
        right_decidable  (bool): False if a loop has net rightward drift, so
                                 max_right is a lower bound, not exact.
    """
    from lexer import tokenize
    from parser import parse, Instruction, Loop

    ast = parse(tokenize(source))
    pos     = [0]
    min_pos = [0]
    max_pos = [0]
    crosses = [False]
    origin_undecidable = [False]
    right_undecidable  = [False]

    def walk(nodes):
        for n in nodes:
            if isinstance(n, Instruction):
                if   n.op == '>': pos[0] += 1
                elif n.op == '<': pos[0] -= 1
                min_pos[0] = min(min_pos[0], pos[0])
                max_pos[0] = max(max_pos[0], pos[0])
                if pos[0] < 0:
                    crosses[0] = True
            elif isinstance(n, Loop):
                entry = pos[0]
                walk(n.body)
                net = pos[0] - entry
                if net < 0:
                    origin_undecidable[0] = True
                elif net > 0:
                    right_undecidable[0] = True 

    walk(ast)
    return {
        "crosses_origin":   crosses[0],
        "min_offset":       min_pos[0],
        "max_right":        max_pos[0],
        "origin_decidable": not origin_undecidable[0],
        "right_decidable":  not right_undecidable[0],
    }


def check_unilateral_safe(source: str) -> None:
    """
    Raise UnilateralTapeError if the program is not safe on Simkin's one-sided
    tape.
    """
    a = analyze_pointer(source)
    if a["crosses_origin"]:
        raise UnilateralTapeError(
            "the program moves the pointer left of the origin (cell 0), which does not exist on Simkin's one-sided tape."
        )
    if not a["origin_decidable"]:
        raise UnilateralTapeError(
            "the program may move the pointer left of the origin inside a loop with net leftward drift; this cannot be ruled out statically, so "
            "it is rejected. Keep the pointer >= 0."
        )


def required_tape_length(source: str, margin: int = 1) -> int:
    """
    Initial tape length needed so the pointer stays on the declared tape: rightmost reachable cell + 1, plus a small margin.
    """
    a = analyze_pointer(source)
    return a["max_right"] + 1 + max(0, margin)


def encode_source(source: str, alphabet_size: int = ALPHABET_SIZE) -> MTProgram:
    """
    Encodes BF source code directly (lexer + parser + encode).

    Convenience function for tests and quick use.

    Parameters:
        source:        BF source code string
        alphabet_size: number of symbols in the tape alphabet (default 2,
                       binary). The Simkin export requires 2.
    """
    from lexer import tokenize
    from parser import parse
    return encode(parse(tokenize(source)), alphabet_size=alphabet_size)

# Alias for compatibility with tm_encoder naming convention
TMProgram = MTProgram
