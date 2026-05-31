"""
Brainfuck_To_Golly_Compiler/compiler/semantic/alphabet_mapper.py
-----------------------------------------------
Second step of phase 4 of the compiler: alphabet reduction

As we've seen any TM with finite alphabet of size N can be simulated by a
binary TM using k=ceil(log2(N)) bits per symbol (for BF: n=256, k=8).

This module is responsible for converting the 256-symbol TMProgram created by
tm_encoder.py to a 8-bit-per-symbol TMProgram.
"""

from compiler.semantic.tm_encoder import Transition, TMProgram, ALPHABET_SIZE, ALPHABET

BITS_PER_SYMBOL = 8
BINARY_ALPHABET = (0,1)

def symbol_to_bits(symbol: int) -> tuple[int, ...]:
    """Encodes symbol {0.255} as 8-bit big-endian tuple (Most Significant Bit at index 0)"""
    if not 0 <= symbol <= 255:
        raise ValueError(f"Symbol {symbol} out of range 0..255")
    return tuple((symbol >> (7-i)) & 1 for i in range(8))

def bits_to_symbol(bits: tuple[int, ...]) -> int:
    """Decodes 8-bit big-endian tuple to symbol {0..255}."""
    if len(bits) != BITS_PER_SYMBOL:
        raise ValueError(f"Expected {BITS_PER_SYMBOL} bits, got {len(bits)}")
    result = 0
    for bit in bits:
        result = (result << 1) | bit
    return result

class MapperError(Exception):
    """Error during alphabet reduction."""
    pass

def map_to_binary(program: TMProgram) -> TMProgram:
    """Transforms a TMProgram over {0..255} into equivalent TMProgram over {0,1}."""
    if program.alphabet_size != ALPHABET_SIZE:
        raise MapperError(f"Expected alphabet_size={ALPHABET_SIZE}, got {program.alphabet_size}.")
    
    binary_transitions: list[Transition] = []
    state_counter = [0]

    def new_state() -> int:
        s = state_counter[0]
        state_counter[0] += 1
        return s
    
    original_states = program.Q
    entry_map = {q: new_state() for q in sorted(original_states)}

    def move_left(from_state: int, to_state: int) -> None:
        """Adds binary transitions moving head one step left."""
        for b in BINARY_ALPHABET:
            binary_transitions.append(Transition(
                state=from_state, read=b,
                new_state=to_state, write=b, direction='L'
            ))

    def move_right(from_state: int, to_state: int) -> None:
        """Adds binary transitions moving head one step right."""
        for b in BINARY_ALPHABET:
            binary_transitions.append(Transition(
                state=from_state, read=b,
                new_state=to_state, write=b, direction='R'
            ))

    def chain_left(start: int, steps: int, end: int) -> None:
        """
        Chains 'steps' left-move transitions from start to end-
        Allocates intermediate states as needed.
        """
        current = start
        for i in range(steps):
            nxt = end if i == steps -1 else new_state()
            move_left(current, nxt)
            current = nxt

    def expand_state(original_state: int) -> None:
        """
        Expands all transitions from one original state into binary
        micro-transitions covering the full read-rewind-write-reposition cycle.
        """
        state_ts = program.transitions_from(original_state)
        if not state_ts:
            return # accept state
        
        entry = entry_map[original_state]

        level: dict[tuple, int] = {(): entry}
        leaf_map: dict[int, int] = {}

        for bit_pos in range(BITS_PER_SYMBOL):
            next_level: dict[tuple, int] = {}
            is_last = (bit_pos == BITS_PER_SYMBOL -1)

            for prefix, src in level.items():
                for bit_val in BINARY_ALPHABET:
                    new_prefix = prefix + (bit_val,)
                    dst = new_state()
                    next_level[new_prefix] = dst

                    binary_transitions.append(Transition(
                        state=src, read=bit_val,
                        new_state=dst, write=bit_val,
                        direction='N' if is_last else 'R'
                    ))

                    if is_last:
                        leaf_map[bits_to_symbol(new_prefix)] = dst
            
            level = next_level

        for symbol, leaf in leaf_map.items():
            original_t = program.transition_for(original_state, symbol)
            if original_t is None:
                continue

            bits_write = symbol_to_bits(original_t.write)
            next_orig = original_t.new_state
            direction = original_t.direction
            is_out = original_t.is_output
            target_entry = entry_map[next_orig]

            rewind_end = new_state()
            chain_left(leaf, BITS_PER_SYMBOL - 1, rewind_end)

            write_current = rewind_end
            for i, bit in enumerate(bits_write):
                is_last_bit = (i == BITS_PER_SYMBOL - 1)
                write_next = new_state()

                for b in BINARY_ALPHABET:
                    binary_transitions.append(Transition(
                        state = write_current,
                        read = b,
                        new_state = write_next,
                        write = bit, 
                        direction = 'N' if is_last_bit else 'R',
                        is_output = is_out and is_last_bit
                    ))

                write_current = write_next
            
            match direction:
                case 'N':
                    chain_left(write_current, BITS_PER_SYMBOL - 1, target_entry)

                case 'R':
                    move_right(write_current, target_entry)

                case 'L':
                    chain_left(write_current, BITS_PER_SYMBOL * 2 -1, target_entry)


    for original_state in sorted(original_states):
        expand_state(original_state)

    return TMProgram(
        transitions = binary_transitions,
        initial_state = entry_map[program.initial_state],
        accept_state = entry_map[program.accept_state],
        num_states = state_counter[0],
        alphabet_size = 2
    )
        
def map_source(source: str) -> TMProgram:
    """
    Full pipeline shorthand: BF source -> binary TMProgram
    
    Applies lexer + parser + tm_encoder + alphabet_mapper.
    """
    from compiler.semantic.tm_encoder import encode_source
    return map_to_binary(encode_source(source))