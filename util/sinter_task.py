import stim
import hashlib
import json
import os
import itertools
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from tqdm import tqdm
from datetime import datetime, timezone, date

import sinter
from mwpf import SinterMWPFDecoder


@dataclass
class TaskMetadata:
    p: float
    d: int
    r: int
    circuit: str
    decoder: str  # e.g. mwpf or pymatching
    decoder_type: Optional[str] = None
    run_id: str = ""

    def __post_init__(self):
        self.run_id = hashlib.sha256(
            json.dumps(asdict(self)).encode("utf-8")
        ).hexdigest()


@dataclass
class TaskConfig:
    circuit: stim.Circuit
    json_metadata: TaskMetadata

    def run_id(self):
        return self.json_metadata.run_id

    def custom_decoders(self):
        return build_custom_decoders([self])


@dataclass
class CollectTasksConfig:
    circuit: str  # circuit name, not instance
    decoder: str  # decoder name, not instance
    decoder_type: Optional[str] = None  # decoder subtype, only used for mwpf decoder
    save_resume_filepath: str = "auto"
    quiet: bool = False
    max_shots: int = 100_000
    max_errors: int = 5_000
    num_workers: int = os.cpu_count() - 2
    task_configs = List[TaskConfig]
    tasks = List[sinter.Task]

    erasure_conversion_factor: float = 0.0

    noise = List[float]
    code_distance = List[int]

    def __post_init__(self):
        if self.decoder == "mwpf" and self.decoder_type is None:
            raise ValueError(
                "Specify decoder_type corresponding to mwpf solver, e.g. SolverSerialJointSingleHair"
            )
        if self.save_resume_filepath == "auto":
            self.save_resume_filepath = generate_save_resume_filepath(self)

    def custom_decoders(self):
        decoders_by_run_id = {}
        for task in self.tasks:
            decoders_by_run_id.update(task.custom_decoders)
        return decoders_by_run_id

    def generate_tasks(self):
        # cartesian product of our parameter sweeps
        parameters = itertools.product(self.code_distance, self.noise)
        for d, p in tqdm(parameters, disable=self.quiet):
            json_metadata = TaskMetadata(
                p=p, d=d, r=3 * d, circuit=self.circuit, decoder=self.decoder
            )
            circuit = stim.Circuit.generated(
                self.circuit,
                rounds=3 * d,
                distance=d,
                # TODO: We assume the same error rate (p) for
                # 1. data qubit depolarization (before_round_data_depolarization)
                # 2. gate application errors (after_clifford_depolarization)
                # in the literature, this noise model is called "circuit-level depolarizing noise"
                # in reality, we know 1 and 2 qubit gates have different error rates.
                # how would we model different error rates for 1 and 2 qubit gates?
                # what if we want to apply erasure conversion only to 2 qubit gate depolarization errors?
                before_round_data_depolarization=p,
                after_clifford_depolarization=p,
                # TODO Realistic SPAM error model
                # We currently assume ideal measurements
                # Implement a noise model that (optionally) includes measurement error
                # before_measure_flip_probability=p_measure
                # We also assume perfect state preparation.
                # Implement a noise model that (optionally) includes reset / state prep error
                # after_reset_flip_probability=p,
                json_metadata=asdict(json_metadata),
            )
            task_config = TaskConfig(circuit=circuit, json_metadata=json_metadata)


def generate_save_resume_filepath(cfg: CollectTasksConfig):
    iso_today = date.today().isoformat()
    # TODO if you run this on a non-Unixlike system (E.g. windows) the path strings will explode
    # Ilyes, if this happens to you on your Windows machine please open a pull request implementing cross-platform Path objects
    # See: https://docs.python.org/3/library/pathlib.html
    basedir = f"datasets/circuit={cfg.circuit}/decoder={cfg.decoder}"
    if cfg.decoder == "pymatching":
        return f"{basedir}/{iso_today}"
    elif cfg.decoder == "mwpf":
        return f"{basedir}/erasure={cfg.erasure_conversion_factor}/solver={cfg.decoder_type}/{iso_today}"
    else:
        raise NotImplemented(
            f"generate_save_resume_filepath not implemented for decoder {cfg.decoder}"
        )


def generate_task_config(
    d: int,
    p: float,
    circuit_variant: str,
    cluster_node_limit: int,
) -> TaskConfig:
    circuit = stim.Circuit.generated(
        circuit_variant,
        rounds=3 * d,
        distance=d,
        before_round_data_depolarization=p,
    )
    json_metadata = {
        "d": d,
        "p": p,
        "label": "rotated_memory_x",
        "r": d * 3,
        "decoder": "mwpf_erasure",
        "cluster_node_limit": cluster_node_limit,
    }
    # collection_options = {"max_shots": max_shots, "max_errors": max_errors}
    run_id = hashlib.sha256(json.dumps(json_metadata).encode("utf-8")).hexdigest()
    json_metadata["run_id"] = run_id
    cfg = TaskConfig(
        circuit=circuit,
        json_metadata=json_metadata,
    )
    return cfg


def generate_run_id(cfg: TaskConfig):
    run_id = hashlib.sha256(json.dumps(cfg.json_metadata).encode("utf-8")).hexdigest()
    return run_id


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


def collect_stats(cfg: CollectTasksConfig) -> List[sinter.TaskStats]:
    return sinter.collect(
        num_workers=cfg.num_workers,
        tasks=cfg.tasks,
        custom_decoders=cfg.custom_decoders(),
        print_progress=cfg.print_progress,
        max_shots=cfg.max_shots,
        max_errors=cfg.max_errors,
        save_resume_filepath=cfg.save_resume_filepath,
    )
