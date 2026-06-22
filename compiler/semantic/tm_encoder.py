"""
compiler/semantic/tm_encoder.py
-------------------------------
Phase 2 of the compiler: Turing-machine encoding and Simkin export.

Responsibility: translate the Brainfuck AST into an explicit Turing Machine
transition table, and serialise it as a "turing rule" string for Michael
Simkin's Golly Turing-machine simulator (turing.py), which performs the
actual Game-of-Life construction.

Pipeline position (the active pipeline):
    BF source → [lexer] → [parser] → [tm_encoder] → Simkin turing rule
                                                  → turing.py (Golly) → GoL

The encoder works over a configurable alphabet. The Simkin path uses a
binary alphabet directly (alphabet_size = 2): the compact two-symbol MTs are
what Simkin's construction expects, so no separate alphabet-reduction step is
needed. compile_to_simkin enforces the binary alphabet (decision E1).

Quintuple format: (state, read, new_state, write, direction)
    state:     current state (int)
    read:      symbol read from tape
    new_state: next state (int)
    write:     symbol written to tape
    direction: head movement — 'L', 'R', 'N' (none / stationary)

The Simkin export removes 'N' moves (eliminate_stationary), turns the accept
state into a bounded two-state halt oscillator, collapses '.' output
(decision B), rejects pointer moves left of the origin on the one-sided tape
(decision A1), and sizes the initial tape to the program's rightward reach
(decision C1).

Design decisions:
    - Wrap-around arithmetic: + and - use modulo alphabet_size, consistent
      with the BF specification.
    - Loop encoding: conditional branching via state splitting.
      Symbol 0 at loop entry → skip body. Symbol != 0 → enter body.
    - MTProgram as result container: encapsulates table + metadata,
      facilitating testing and downstream processing.
"""

from dataclasses import dataclass, field
from parser import Instruction, Loop, AST


# ── ALPHABET ──────────────────────────────────────────────────────────────────

# Default alphabet size. The active (Simkin) pipeline always uses 2; this
# default is kept only so encode() can be exercised over a larger alphabet in
# isolation. compile_to_simkin enforces alphabet_size == 2 (decision E1).
ALPHABET_SIZE = 2
ALPHABET      = tuple(range(ALPHABET_SIZE))


# ── DATA STRUCTURES ───────────────────────────────────────────────────────────


@dataclass
class Transition:
    """
    A single MT transition rule (quintuple).

    Represents one rule of the transition function δ:
        δ(state, read) = (new_state, write, direction)

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
        """Returns all transitions departing from a given state."""
        return [t for t in self.transitions if t.state == state]

    def transition_for(self, state: int, symbol: int) -> 'Transition | None':
        """Returns the unique transition for (state, symbol), or None."""
        for t in self.transitions:
            if t.state == state and t.read == symbol:
                return t
        return None

    def is_deterministic(self) -> bool:
        """
        Verifies that the TM is deterministic:
        at most one transition per (state, symbol) pair.
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
        return [t for t in self.transitions if t.is_output]

    # ── Formal MT components ──────────────────────────────────────────────────
    # Reconstruct the components of the formal 7-tuple
    # M = (Q, Σ, Γ, δ, q₀, q_accept, q_reject) that are implicit in the table.

    @property
    def Q(self) -> set[int]:
        """
        Q — complete set of states.

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
        Γ — tape alphabet.

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
        Σ — input alphabet.

        Symbols appearing as read values in transitions from the
        initial state. In practice equals tape_alphabet for BF programs
        since any cell value can be under the head at any point.
        """
        return {t.read for t in self.transitions_from(self.initial_state)}

    def as_formal_tuple(self) -> dict:
        """
        Returns a dict representing the formal 7-tuple components.

        Useful for documentation, debugging and verifying correspondence
        with the theoretical definition in Chapter 2 of the thesis.

        Returns:
            dict with keys: Q, Sigma, Gamma, q0, q_accept, num_transitions
        """
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
                        # Move head right or left — symbol unchanged
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
                        # Increment cell with wrap-around mod alphabet_size
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
                        # Decrement cell with wrap-around mod alphabet_size
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
                        # Output current cell value — symbol unchanged
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
                # ── Loop encoding ──────────────────────────────────────────
                #
                # loop_entry (= current):
                #   read 0      → loop_exit   (skip body)
                #   read s > 0  → body_entry  (enter body)
                #
                # [body states encoded recursively]
                #
                # body_last:
                #   any symbol  → loop_entry  (re-evaluate condition)
                #
                # loop_exit:
                #   continues with next instruction

                loop_entry = current
                body_entry = new_state()
                loop_exit  = new_state()

                # Conditional entry transitions
                transitions.append(Transition(
                    state=loop_entry, read=0,
                    new_state=loop_exit, write=0, direction='N'
                ))
                for sym in alphabet[1:]:   # symbols != 0 enter the body
                    transitions.append(Transition(
                        state=loop_entry, read=sym,
                        new_state=body_entry, write=sym, direction='N'
                    ))

                # Encode body recursively
                if node.body:
                    body_last = encode_nodes(node.body, body_entry)
                else:
                    body_last = body_entry

                # Unconditional back-edge: body_last → loop_entry
                for sym in alphabet:
                    transitions.append(Transition(
                        state=body_last, read=sym,
                        new_state=loop_entry, write=sym, direction='N'
                    ))

                current = loop_exit

        return current

    # ── Main encoding ──────────────────────────────────────────────────────
    initial = new_state()   # q0
    last    = encode_nodes(ast, initial)

    # Connect last state to accept on any symbol
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


# ── STATIONARY-MOVE ELIMINATION ───────────────────────────────────────────────

def eliminate_stationary(program: MTProgram) -> MTProgram:
    """
    Return an equivalent MTProgram with no stationary ('N') head moves,
    using only 'L' and 'R'.

    Why: some Turing-machine simulators (e.g. Michael Simkin's GoL
    simulator) implement head motion physically and accept only left/right
    moves. BF naturally produces many stationary transitions (incrementing a
    cell does not move the pointer), so they must be removed before export.

    Technique (a standard equivalence, see Sipser, *Introduction to the
    Theory of Computation*): a stationary transition

        δ(s, r) = (s', w, N)

    is replaced by a right step into a fresh auxiliary state followed by a
    left step back:

        δ(s,    r) = (s_aux, w, R)          write w, step right
        δ(s_aux, x) = (s',   x, L)   ∀x      read anything, step back left

    Net effect: w is written in the original cell, the head returns to its
    original position, and control passes to s'. One auxiliary state is
    created per stationary transition; the auxiliary needs a rule for every
    tape symbol (it leaves the cell unchanged on the way back).

    The transformation preserves the computed result: for every input, the
    transformed machine halts on the accept state with the same final tape
    contents (verified against the reference interpreter in the tests).

    Parameters:
        program: an MTProgram that may contain 'N' transitions.

    Returns:
        An equivalent MTProgram whose transitions use only 'L' and 'R'.
        If the input already has no 'N' transitions, an equivalent program
        is returned unchanged in behaviour.
    """
    alphabet = list(range(program.alphabet_size))

    # Fresh state ids continue after the existing ones.
    next_state = [program.num_states]

    def new_state() -> int:
        s = next_state[0]
        next_state[0] += 1
        return s

    new_transitions: list[Transition] = []

    for t in program.transitions:
        if t.direction != 'N':
            # Left/right transitions pass through unchanged.
            new_transitions.append(t)
            continue

        # Stationary transition: split into right-step + left-step-back.
        aux = new_state()

        # 1) write w, step right into the auxiliary state.
        new_transitions.append(Transition(
            state=t.state, read=t.read,
            new_state=aux, write=t.write, direction='R',
            is_output=t.is_output,
        ))

        # 2) from the auxiliary state, for EVERY symbol, leave it unchanged
        #    and step left back to the original cell, entering s'.
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


# ── SIMKIN TURING-RULE EXPORT ─────────────────────────────────────────────────

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

    where the columns map from our Transition as:
        tape     = read        (symbol under the head)
        head     = state       (current state)
        new_tape = write       (symbol written)
        new_head = new_state   (next state)
        l/r      = direction   ('L' -> 'l', 'R' -> 'r')

    Requirements enforced here:
      * No 'N' moves. The program must already be stationary-free; call
        eliminate_stationary() first. A ValueError is raised otherwise,
        because Simkin only understands left/right.
      * Complete table. Simkin aborts if any (state, symbol) combination is
        missing. Simkin's machine also has no halt — it applies the table
        forever — so the accept state is turned into a two-state oscillator
        (accept ⇄ accept_partner, stepping right then left over two cells,
        rewriting each symbol unchanged). This keeps the head bounded next to
        the final tape without a stationary move and without marching off the
        one-sided tape. Any other missing combination is filled with a
        harmless self-loop.
      * Head start state is 0. Our encoder already uses initial_state 0,
        which Simkin requires; this is asserted.

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

    # Bounded halt: Simkin's machine never stops — it applies the table
    # forever, with head motion realised physically (only l/r, no stationary
    # "stay"). A naive accept self-loop with direction 'r' would march the
    # head rightward off the end of the finite one-sided tape, corrupting the
    # result. Instead the accept state is turned into a two-state oscillator:
    #
    #     accept           reads s → accept_partner, write s, R
    #     accept_partner   reads s → accept,         write s, L
    #
    # The head steps right then left between two cells forever, writing each
    # symbol back unchanged, so it stays bounded next to the final tape
    # contents without ever disturbing them. This is the same Sipser-style
    # "split an N move into R then L" trick used by eliminate_stationary,
    # applied to the halt. accept_partner is a fresh state appended after the
    # existing ones.
    accept         = program.accept_state
    accept_partner = program.num_states          # one fresh state id

    states   = range(program.num_states + 1)     # include accept_partner
    symbols  = range(program.alphabet_size)

    # Index existing transitions by (state, read).
    table = {(t.state, t.read): t for t in program.transitions}

    lines = []
    # Line 1: input tape.
    lines.append(" ".join(str(s) for s in input_tape))
    # Line 2: head start location.
    lines.append(str(head_start))

    # One line per (state, symbol). Simkin needs the full table.
    for state in states:
        for sym in symbols:
            if state == accept:
                # Halt oscillator, first half: step right into the partner.
                new_state = accept_partner
                write     = sym
                direction = 'r'
            elif state == accept_partner:
                # Halt oscillator, second half: step left back to accept.
                new_state = accept
                write     = sym
                direction = 'l'
            else:
                t = table.get((state, sym))
                if t is None:
                    # Any other missing combination: harmless self-loop.
                    # Not reachable on a well-formed run, but Simkin requires
                    # a complete table.
                    new_state = state
                    write     = sym
                    direction = 'r'
                else:
                    new_state = t.new_state
                    write     = t.write
                    direction = t.direction.lower()
            # Columns: tape head new_tape new_head l/r
            lines.append(f"{sym} {state} {write} {new_state} {direction}")

    return "\n".join(lines)


# ── SIMKIN EXPORT DRIVER ──────────────────────────────────────────────────────

def compile_to_simkin(source: str,
                      alphabet_size: int = 2,
                      input_tape: list = None,
                      head_start: int = 0) -> str:
    """
    End-to-end: BF source → stationary-free MT → Simkin turing-rule string.

    Runs the full phase-1/phase-2 pipeline, collapses '.' (decision B),
    eliminates stationary moves, and produces a string ready for Simkin's
    Golly simulator.

    Unilateral-tape safety (decision A1): Simkin's tape is one-sided, with
    nothing left of cell 0. A BF program that moves the pointer left of the
    origin is a compile error — there is no auto-shifting of the origin.
    check_unilateral_safe raises UnilateralTapeError for such programs (both
    a concrete crossing and a loop with net leftward drift that may cross).

    Tape sizing (decision C1): if input_tape is not given, the initial tape
    is all zeros with length required_tape_length(source) — the rightmost
    cell the program reaches, plus margin — so the pointer stays on the
    declared tape. The pointer starts at the origin (head_start default 0),
    which is always valid since '<' below 0 is rejected.

    Parameters:
        source:        BF source code.
        alphabet_size: tape alphabet size; must be 2 (decision E1, binary).
        input_tape:    initial tape (default: zeros sized to the program).
        head_start:    head start location (default 0, the origin).

    Returns:
        A Simkin turing-rule string.

    Raises:
        UnilateralTapeError: if the program may move left of the origin (A1).
        ValueError:          if alphabet_size != 2 (E1).
    """
    # Decision E1: the Simkin construction is binary.
    if alphabet_size != 2:
        raise ValueError(
            f"the Simkin export is binary only (alphabet_size must be 2, "
            f"got {alphabet_size}). Decision E1."
        )

    # Decision A1: reject any pointer move left of the origin. No auto-shift.
    check_unilateral_safe(source)

    # Decision C1: size the initial tape to the program's rightward reach.
    if input_tape is None:
        input_tape = [0] * required_tape_length(source)

    # Build the MT for the Simkin path. '.' is collapsed here (decision B):
    # the rendered tape is the output, so output instructions must not become
    # MT transitions. encode_source / the parser are left untouched; we filter
    # the AST in between so only the Simkin path is affected.
    from lexer import tokenize
    from parser import parse
    ast = strip_output_nodes(parse(tokenize(source)))
    mt = encode(ast, alphabet_size=alphabet_size)
    mt = eliminate_stationary(mt)
    return to_simkin_rule(mt, input_tape=input_tape, head_start=head_start)


# ── CONVENIENCE ───────────────────────────────────────────────────────────────

# ── OUTPUT COLLAPSE (Simkin path only) ────────────────────────────────────────

def strip_output_nodes(ast):
    """
    Return a copy of the AST with every '.' (output) instruction removed,
    recursively, including inside loops.

    Rationale (decision B): in the Simkin export the *tape itself*, rendered
    in Golly, is the output — there is no separate output stream. So '.' must
    not become a transition in the exported MT. This collapse is applied ONLY
    on the Simkin path (compile_to_simkin); the reference interpreter and the
    manual-wiring pipeline keep '.' as a real output instruction, since they
    rely on it to validate program output.

    The parser and encode() are left untouched; this filters the AST in
    between, so no shared component changes behaviour.

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
                continue                       # drop the output instruction
            result.append(node)
        elif isinstance(node, Loop):
            result.append(Loop(body=strip_output_nodes(node.body)))
        else:
            result.append(node)
    return result


# ── POINTER ANALYSIS (unilateral-tape safety + tape sizing) ───────────────────

class UnilateralTapeError(Exception):
    """
    The BF program may move the pointer left of the origin (cell 0), which
    cannot be placed on Simkin's one-sided tape. Decision A1: this is a
    compile error, not something to work around.
    """


def analyze_pointer(source: str) -> dict:
    """
    Static pointer analysis for the Simkin export.

    Simkin's tape is one-sided: it extends rightward from cell 0 and there is
    nothing left of the origin. Decision A1 makes any pointer move left of
    cell 0 a compile error. Decision C1 sizes the initial tape from the
    rightmost cell the program reaches.

    The analysis distinguishes two kinds of loop drift:
      * Net LEFTWARD drift inside a loop ('<' dominates): repeating the loop
        can push the pointer arbitrarily far left, so it may cross the origin.
        Since the repeat count is not statically known, origin-crossing is
        undecidable and treated conservatively as unsafe (A1 reject).
      * Net RIGHTWARD drift ('>' dominates): repeating the loop only moves
        right, which is always safe on a one-sided tape (the tape grows
        rightward). This is NOT rejected; it only means the exact rightmost
        cell is not statically known, so the tape length must be treated as
        "at least max_right + 1".

    For loop-free programs (the demonstrable scope) every figure is exact.

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
                    origin_undecidable[0] = True   # may cross origin if repeated
                elif net > 0:
                    right_undecidable[0] = True     # safe, but max_right unbounded

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
    tape (decision A1): either a concrete move crosses the origin, or a loop
    with net leftward drift may cross it when repeated.

    Mentions the (deliberately unimplemented) wrap-around alternative, which
    would be disproportionate: emulating wrap to the last cell needs O(N)
    extra states per boundary '<' on a fixed-length-N tape.
    """
    a = analyze_pointer(source)
    if a["crosses_origin"]:
        raise UnilateralTapeError(
            "the program moves the pointer left of the origin (cell 0), which "
            "does not exist on Simkin's one-sided tape. This is a documented "
            "limitation (decision A1). A wrap-around to the last cell is "
            "possible but disproportionate (O(N) states per boundary '<' on a "
            "fixed-length tape), so it is not implemented."
        )
    if not a["origin_decidable"]:
        raise UnilateralTapeError(
            "the program may move the pointer left of the origin inside a loop "
            "with net leftward drift; this cannot be ruled out statically, so "
            "it is rejected (decision A1). Keep the pointer >= 0."
        )


def required_tape_length(source: str, margin: int = 1) -> int:
    """
    Initial tape length needed so the pointer stays on the declared tape
    (decision C1): rightmost reachable cell + 1, plus a small margin.

    Exact for loop-free programs. If a loop has net rightward drift the value
    is a lower bound (right_decidable is False in analyze_pointer); callers
    that need a guarantee should cap loop programs or supply their own length.
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
