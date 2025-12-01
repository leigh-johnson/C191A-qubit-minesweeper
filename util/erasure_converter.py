from dataclasses import replace
from typing import Iterable, List

import stim
import sinter
import mwpf.ref_circuit
from util.sinter_task import TaskConfig

CONVERT_INSTRUCTIONS = ("DEPOLARIZE1", "DEPOLARIZE2")


class CustomCircuit(stim.Circuit):
    heralded_detector_indices = []


def filter_convert_to_erasure_instructions(
    circuit: Iterable[stim.CircuitInstruction],
    convert_instructions=CONVERT_INSTRUCTIONS,
):
    return filter(lambda instruction: instruction.name in convert_instructions, circuit)


def convert_circuit_errors_to_erasures_v1(
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
            if conversion_factor < 1:
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


def convert_circuit_errors_to_erasures_v2(
    circuit: stim.Circuit,
    conversion_factor: float = 1.0,
    add_detectors: bool = True,
    convert_instructions: Iterable[str] = CONVERT_INSTRUCTIONS,
) -> CustomCircuit:
    """Converts random Pauli noise instructions (e.g. DEPOLARIZE1/2) to HERALDED_ERASE.

    This version is self-contained and does *not* depend on mwpf.ref_circuit.

    Behavior:
      * For each instruction with name in `convert_instructions` and probability p:
          - If conversion_factor < 1:
                keep a residual Pauli noise with probability p * (1 - conversion_factor)
          - Add HERALDED_ERASE with probability min(1, 4/3 * p * conversion_factor)
            on the same targets.
      * All other instructions are copied verbatim.
      * json_metadata.p_erase is set to conversion_factor * p (p taken from the last
        converted instruction, matching your original code’s behavior).
        * When add_detectors=True, we insert a single DETECTOR per HERALDED_ERASE,
          using a generic `rec[-1]` target.

    """

    new_circuit = CustomCircuit()

    convert_instructions = set(convert_instructions)
    # Track which detector indices correspond to heralds.
    herald_detector_indices: List[int] = []
    # Current detector index while we rebuild.
    current_det_index = 0
    for inst in circuit:
        name = inst.name

        # CircuitRepeatBlock vs CircuitInstruction:
        if isinstance(inst, stim.CircuitRepeatBlock):
            # convert noise *inside* repeat blocks is probably easier to do at the circuit declaration level
            # For now, we just copy the block as-is.
            new_circuit.append(inst)
            # Update detector index: each repetition contributes body.num_detectors.
            body = inst.body_copy()
            current_det_index += body.num_detectors * inst.repeat_count
            continue

        # Normal instruction
        gate_args = inst.gate_args_copy()
        if name in convert_instructions and gate_args:
            # Example: DEPOLARIZE1(p) q0, q1, ...
            p = float(gate_args[0])

            # 1. Optional residual Pauli noise (for the fraction not converted)
            if conversion_factor < 1.0:
                residual_p = p * (1.0 - conversion_factor)
                if residual_p > 0.0:
                    new_circuit.append(
                        name,
                        inst.targets_copy(),
                        residual_p,
                    )

            # 2. Heralded erase for the converted part
            p_erase = min(1.0, (4.0 / 3.0) * p * conversion_factor)
            if p_erase > 0.0:
                new_circuit.append(
                    "HERALDED_ERASE", inst.targets_copy(), p_erase, tag="heralded_erase"
                )

                # 3. Optional DETECTOR(s) to expose herald bits.
                if add_detectors:
                    # Immediately after HERALDED_ERASE, rec[-1] is *its* herald bit.
                    new_circuit.append("DETECTOR", [stim.target_rec(-1)])
                    herald_detector_indices.append(current_det_index)
                    current_det_index += 1

        else:
            # Pass through untouched
            new_circuit.append(inst)

    new_circuit.heralded_detector_indices = herald_detector_indices

    return new_circuit


def convert_task_config_to_erasures(
    task_config: TaskConfig,
    conversion_factor: float = 1.0,
    add_detectors: bool = True,
    convert_instructions: Iterable[str] = CONVERT_INSTRUCTIONS,
):
    json_metadata = task_config.json_metadata
    converted_circuit = convert_circuit_errors_to_erasures_v2(
        task_config.circuit,
        conversion_factor=conversion_factor,
        add_detectors=add_detectors,
    )
    # TODO this only works conversion_factor = 1
    setattr(json_metadata, "p_erase", json_metadata.p)
    return TaskConfig(
        circuit=converted_circuit,
        json_metadata=json_metadata,
        quiet=task_config.quiet,
    )
