import mwpf.ref_circuit
from dataclasses import replace
from dataclasses import dataclass, asdict
import stim
from typing import Iterable

CONVERT_INSTRUCTIONS = ("DEPOLARIZE1", "DEPOLARIZE2")


@dataclass
class TaskConfig:
    circuit: stim.Circuit
    json_metadata: dict


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
    converted_metadata = json_metadata.copy()
    converted_metadata["p_erase"] = converted_metadata["p"]
    converted_circuit = mwpf.ref_circuit.RefCircuit.of(instructions).circuit()

    new_task_config = TaskConfig(
        circuit=converted_circuit,
        json_metadata=converted_metadata,
    )
    return new_task_config
