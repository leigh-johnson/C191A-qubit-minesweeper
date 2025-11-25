import itertools
from uuid import uuid4
import json

from dataclasses import replace
import mwpf.ref_circuit

import hashlib
import sinter
import stim
from mwpf import SinterMWPFDecoder
import matplotlib.pyplot as plt
import os

from tqdm.notebook import tqdm

CONVERT_TO_ERASURE_NOISE = ("DEPOLARIZE1", "DEPOLARIZE2")
noise = [0.01, 0.02, 0.03, 0.04, 0.05, 0.07, 0.08, 0.09, 0.1, 0.2, 0.3]
noise = [
    0.001,
    0.004,
    0.005,
    0.006,
    0.0065,
    0.007,
    0.0075,
    0.008,
    0.009,
    0.01,
    0.011,
]
code_distance = [3, 5, 7, 9, 11, 13, 15]
MAX_SHOTS = 10_000
MAX_ERRORS = 1_000


def erasure_conversion(
    task_config: dict, conversion_factor: int = 1, add_detectors: bool = True
) -> dict:
    """Converts random pauli noise instructions (e.g. DEPOLARIZE1, DEPOLARIZE2) to HERALDED_ERASE instructions

    See notes in https://github.com/yuewuo/mwpf/blob/main/src/python/mwpf/ref_circuit.py
    for explanation of why reference circuits are needed to keep track of measurement indices w/ heralded errors
    """
    circuit = task_config["circuit"]
    json_metadata = task_config["json_metadata"]
    ref_circuit = mwpf.ref_circuit.RefCircuit.of(circuit)

    instructions: list[mwpf.ref_circuit.RefInstruction] = []
    for instruction in ref_circuit:
        if instruction.name in CONVERT_TO_ERASURE_NOISE:
            p = instruction.gate_args[0]
            instructions.append(replace(instruction, gate_args=[p * conversion_factor]))
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

    new_task_config = dict(
        circuit=converted_circuit,
        json_metadata=converted_metadata,
    )
    return new_task_config


def generate_task_config(d, p):
    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_x",
        rounds=3 * d,  # since we have perfect measurements, run 1 round
        distance=d,
        before_round_data_depolarization=p,
    )
    cluster_node_limit = 50
    # max_shots = 50_000
    # max_errors = 2_000
    # max_shots = 10000
    # max_errors = 100
    # elif d >= 7:
    #     cluster_node_limit = 100
    #     max_shots = 10_000
    #     max_errors = 1_000
    json_metadata = {
        "d": d,
        "p": p,
        "label": "rotated_memory_x",
        "r": d * 3,
        "decoder": "mwpf_erasure",
        "cluster_node_limit": cluster_node_limit,
    }
    # collection_options = {"max_shots": max_shots, "max_errors": max_errors}
    run_id = hashlib.sha256(json.dumps(json_metadata))
    json_metadata["run_id"] = run_id
    cfg = dict(
        circuit=circuit,
        json_metadata=json_metadata,
        # collection_options=collection_options,
    )
    erasure_cfg = erasure_conversion(cfg)
    task = sinter.Task(**erasure_cfg, decoder=f"mwpf__{run_id}")
    return task


def build_custom_decoders(task_configs):
    return {
        f"mwpf__{task.json_metadata['run_id']}": SinterMWPFDecoder(
            decoder_type="SolverSerialJointSingleHair",
            cluster_node_limit=task.json_metadata["cluster_node_limit"],
            with_progress=True,
            timeout=10,
        ).with_circuit(task.circuit)
        for task in task_configs
    }


def collect_erasure_stats(code_distance, noise):
    pbar = tqdm(code_distance)
    results = []
    for d in pbar:
        pbar.set_description(f"Collecting d={d}")
        tasks = list(generate_task_config(d, p) for p in noise)
        custom_decoders = build_custom_decoders(tasks)

        erasure_collected_stats = sinter.collect(
            num_workers=os.cpu_count() - 4,
            tasks=tasks,
            custom_decoders=custom_decoders,
            print_progress=True,
            max_shots=MAX_SHOTS,
            max_errors=MAX_ERRORS,
            save_resume_filepath=f"../datasets/rotated_memory_x_mwpf_SolverSerialJointSingleHair_erasure/2025_11_24_pthresh__d={d}.csv",
        )
        results.append(erasure_collected_stats)
    return results


erasure_collected_stats = collect_erasure_stats(code_distance, noise)
