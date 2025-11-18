from dataclasses import dataclass
from typing import List
import re

_HEADER_RE = re.compile(
    r"""
    ^\#.*\n                                           # first comment line (ignore content)
    ^\#\s*task:\s*(?P<task>\S+)\s*\n
    ^\#\s*rounds:\s*(?P<rounds>\d+)\s*\n
    ^\#\s*distance:\s*(?P<distance>\d+)\s*\n
    ^\#\s*before_round_data_depolarization:\s*
        (?P<brdd>[-+]?\d*\.?\d+)\s*\n
    ^\#\s*before_measure_flip_probability:\s*
        (?P<bmp>[-+]?\d*\.?\d+)\s*\n
    ^\#\s*after_reset_flip_probability:\s*
        (?P<arfp>[-+]?\d*\.?\d+)\s*\n
    ^\#\s*after_clifford_depolarization:\s*
        (?P<acd>[-+]?\d*\.?\d+)\s*\n
    ^\#\s*layout:\s*\n
    (?P<layout>(?:^\#.*\n)*)                         # all layout lines until Legend
    ^\#\s*Legend:\s*\n
    (?P<legend>(?:^\#.*\n?)*)                      # legend to end of string
    """,
    re.MULTILINE | re.VERBOSE,
)

@dataclass
class CircuitParams:
    task: str
    rounds: int
    distance: int
    before_round_data_depolarization: float
    before_measure_flip_probability: float
    after_reset_flip_probability: float
    after_clifford_depolarization: float
    layout: List[str]
    legend: str

def _strip_hash_prefix(block: str) -> List[str]:
    """Convert a block of '# ...' lines into cleaned strings."""
    return [line.replace("#", "") for line in block.splitlines()]

def parse_stim_generated_header(header: str):
    m = _HEADER_RE.match(header)
    if not m:
        raise ValueError("Header did not match expected format")

    layout_lines = _strip_hash_prefix(m.group("layout"))
    legend_lines = _strip_hash_prefix(m.group("legend"))
    legend_text = "\n".join(legend_lines)

    return CircuitParams(
        task=m.group("task"),
        rounds=int(m.group("rounds")),
        distance=int(m.group("distance")),
        before_round_data_depolarization=float(m.group("brdd")),
        before_measure_flip_probability=float(m.group("bmp")),
        after_reset_flip_probability=float(m.group("arfp")),
        after_clifford_depolarization=float(m.group("acd")),
        layout=layout_lines,
        legend=legend_text,
    )