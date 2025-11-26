from dataclasses import replace
from typing import Iterable

import stim
import sinter
import mwpf.ref_circuit

from util.sinter_task import TaskConfig

CONVERT_INSTRUCTIONS = ("DEPOLARIZE1", "DEPOLARIZE2")


def filter_convert_to_erasure_instructions(
    circuit: Iterable[stim.CircuitInstruction],
    convert_instructions=CONVERT_INSTRUCTIONS,
):
    return filter(lambda instruction: instruction.name in convert_instructions, circuit)


def convert_circuit_errors_to_erasures(
    task_config: dict,
    conversion_factor: int = 1,
    add_detectors: bool = True,
    convert_instructions=CONVERT_INSTRUCTIONS,
) -> TaskConfig:
    """Converts random pauli noise instructions (e.g. DEPOLARIZE1, DEPOLARIZE2) to HERALDED_ERASE instructions

    See notes in https://github.com/yuewuo/mwpf/blob/main/src/python/mwpf/ref_circuit.py
    for explanation of why reference circuits are needed to keep track of measurement indices w/ heralded errors
    """
    circuit = task_config.circuit
    json_metadata = task_config.json_metadata
    ref_circuit = mwpf.ref_circuit.RefCircuit.of(circuit)

    instructions: list[mwpf.ref_circuit.RefInstruction] = []
    for instruction in ref_circuit:
        if instruction.name in convert_instructions:
            p = instruction.gate_args[0]
            instructions.append(
                replace(instruction, gate_args=[p * (1 - conversion_factor)])
            )
            new_instruction = mwpf.ref_circuit.RefInstruction.new_heralded_erase(
                instruction.targets, min(1, 4 / 3 * p * conversion_factor)
            )
            instructions.append(new_instruction)
            if add_detectors is True:
                for rec in new_instruction.recs:
                    instructions.append(
                        mwpf.ref_circuit.RefInstruction.new_detector((rec,))
                    )
        else:
            instructions.append(instruction)
    json_metadata.p_erase = conversion_factor * p
    converted_circuit = mwpf.ref_circuit.RefCircuit.of(instructions).circuit()

    new_task_config = TaskConfig(
        circuit=converted_circuit,
        json_metadata=json_metadata,
        quiet=task_config.quiet,
    )
    return new_task_config


def generate_erasure_task_config(
    cfg: TaskConfig, conversion_factor: int
) -> sinter.Task:
    erasure_cfg = convert_circuit_errors_to_erasures(cfg, conversion_factor)
    task = sinter.Task(**erasure_cfg, decoder=f"mwpf__{erasure_cfg.run_id}")
    return task
