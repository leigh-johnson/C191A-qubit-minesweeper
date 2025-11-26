import stim
import hashlib
import json
import os
import itertools
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Union
from tqdm import tqdm
from datetime import datetime, timezone, date
from pathlib import Path
from enum import StrEnum

import sinter
from mwpf import SinterMWPFDecoder
from util.erasure_converter import convert_circuit_errors_to_erasures


class DecoderLib(StrEnum):
    PYMATCHING = "pymatching"
    MWPF = "mwpf"

    def __str__(self):
        return self.value


class MWPFSolverType(StrEnum):
    """
    See: https://github.com/yuewuo/mwpf/blob/main/src/mwpf_solver.rs
    """

    SolverSerialJointSingleHair = "SolverSerialJointSingleHair"
    SolverSerialSingleHair = "SolverSerialSingleHair"
    SolverSerialUnionFind = "SolverSerialUnionFind"

    def __str__(self):
        return self.value


@dataclass
class TaskMetadata:
    p: float
    d: int
    r: int
    circuit: str
    decoder: DecoderLib  # e.g. mwpf or pymatching
    decoder_type: Optional[MWPFSolverType] = None
    run_id: str = ""
    cluster_node_limit: Optional[int] = None
    p_erase: float = 0.0

    def __post_init__(self):
        self.run_id = hashlib.sha256(
            json.dumps(asdict(self)).encode("utf-8")
        ).hexdigest()


@dataclass
class TaskConfig:
    circuit: stim.Circuit
    json_metadata: TaskMetadata
    custom_decoders: Optional[Dict[str, SinterMWPFDecoder]] = None
    quiet: bool = False

    def __post_init__(self):
        self.run_id = hashlib.sha256(
            json.dumps(asdict(self.json_metadata)).encode("utf-8")
        ).hexdigest()
        if self.json_metadata.decoder is DecoderLib.MWPF:
            self.custom_decoders = build_custom_decoders(
                self, with_progress=not self.quiet
            )

    def run_id(self):
        return self.json_metadata.run_id

    def to_task(self):
        if self.json_metadata.decoder is DecoderLib.PYMATCHING:
            return sinter.Task(
                circuit=self.circuit,
                json_metadata=asdict(self.json_metadata),
            )
        elif self.json_metadata.decoder == DecoderLib.MWPF:
            return sinter.Task(
                circuit=self.circuit,
                json_metadata=asdict(self.json_metadata),
                decoder=list(self.custom_decoders)[0],
            )
        else:
            raise NotImplemented


@dataclass
class CollectTasksConfig:
    circuit: str  # circuit name, not instance
    decoder: DecoderLib  # decoder name, not instance
    noise: tuple[float]
    code_distance: tuple[int]
    task_configs: List[TaskConfig] = field(default_factory=list)
    tasks: List[sinter.Task] = field(default_factory=list)
    decoder_type: Optional[MWPFSolverType] = (
        None  # decoder subtype, only used for mwpf decoder
    )
    save_resume_filepath: Union[str, Path] = "auto"
    quiet: bool = False
    max_shots: int = 100_000
    max_errors: int = 5_000
    num_workers: int = os.cpu_count() - 2
    erasure_conversion_factor: float = 0.0
    cluster_node_limit: Optional[int] = None

    def __post_init__(self):
        if self.decoder is DecoderLib.MWPF and self.decoder_type is None:
            raise ValueError(
                "Specify decoder_type corresponding to mwpf solver, e.g. SolverSerialJointSingleHair"
            )
        if self.save_resume_filepath == "auto":
            self.save_resume_filepath = generate_save_resume_filepath(self)
            os.makedirs(Path(self.save_resume_filepath).parent, exist_ok=True)
        self.generate_tasks()

    def custom_decoders(self):
        decoders_by_run_id = {}
        for task in self.task_configs:
            if task.custom_decoders:
                decoders_by_run_id.update(task.custom_decoders)
        return decoders_by_run_id

    def generate_tasks(self):
        # cartesian product of our parameter sweeps
        parameters = itertools.product(self.code_distance, self.noise)
        for d, p in tqdm(parameters, disable=self.quiet):
            json_metadata = TaskMetadata(
                p=p,
                d=d,
                r=3 * d,
                circuit=self.circuit,
                decoder=self.decoder,
                decoder_type=self.decoder_type,
                cluster_node_limit=self.cluster_node_limit,
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
            )
            task_config = TaskConfig(
                circuit=circuit, json_metadata=json_metadata, quiet=self.quiet
            )
            if self.erasure_conversion_factor > 0:
                if self.decoder is not DecoderLib.MWPF:
                    raise NotImplemented(
                        f"MWPF decoder is required for nonzero erasure_conversion_factor"
                    )
                task_config = convert_circuit_errors_to_erasures(
                    task_config, self.erasure_conversion_factor
                )
            task = task_config.to_task()
            self.task_configs.append(task_config)
            self.tasks.append(task)


def generate_save_resume_filepath(cfg: CollectTasksConfig):
    iso_today = date.today().isoformat()
    basedir = os.path.join(
        "datasets", f"circuit={cfg.circuit}", f"decoder={cfg.decoder}"
    )
    if cfg.decoder == DecoderLib.PYMATCHING:
        return Path(os.path.join(basedir, f"{iso_today}.csv"))
    elif cfg.decoder == DecoderLib.MWPF:
        return Path(
            os.path.join(
                basedir,
                f"erasure={cfg.erasure_conversion_factor}",
                f"solver={cfg.decoder_type}",
                f"{iso_today}.csv",
            )
        )
    else:
        raise NotImplemented(
            f"generate_save_resume_filepath not implemented for decoder {cfg.decoder}"
        )


def generate_run_id(cfg: TaskConfig):
    run_id = hashlib.sha256(json.dumps(cfg.json_metadata).encode("utf-8")).hexdigest()
    return run_id


def build_custom_decoders(cfg: TaskConfig, with_progress: bool = True):
    return {
        f"mwpf__{cfg.run_id}": SinterMWPFDecoder(
            decoder_type="SolverSerialJointSingleHair",
            cluster_node_limit=cfg.json_metadata.cluster_node_limit,
            with_progress=with_progress,
            timeout=10,
        ).with_circuit(cfg.circuit)
    }


def collect_stats(cfg: CollectTasksConfig) -> List[sinter.TaskStats]:
    custom_decoders = cfg.custom_decoders()
    return sinter.collect(
        num_workers=cfg.num_workers,
        tasks=cfg.tasks,
        decoders=[cfg.decoder],
        custom_decoders=custom_decoders,
        print_progress=not cfg.quiet,
        max_shots=cfg.max_shots,
        max_errors=cfg.max_errors,
        save_resume_filepath=cfg.save_resume_filepath,
    )
