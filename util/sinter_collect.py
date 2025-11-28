import hashlib
import json
import os
import itertools
from typing import Optional, Union, List
from dataclasses import dataclass, field
from pathlib import Path
from datetime import date

import sinter
import stim
from tqdm import tqdm

from util.erasure_converter import convert_circuit_errors_to_erasures

from util.sinter_task import (
    DecoderLib,
    MWPFSolverType,
    TaskMetadata,
    TaskConfig,
)


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
    num_rounds: Optional[int] = None
    num_rounds_factor: int = 1
    verbose: bool = False

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
            if self.num_rounds is None:
                num_rounds = int(d * self.num_rounds_factor)
            else:
                num_rounds = self.num_rounds
            json_metadata = TaskMetadata(
                p=p,
                d=d,
                r=num_rounds,
                circuit=self.circuit,
                decoder=self.decoder,
                decoder_type=self.decoder_type,
                cluster_node_limit=self.cluster_node_limit,
            )
            circuit = stim.Circuit.generated(
                self.circuit,
                rounds=num_rounds,
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
                circuit=circuit,
                json_metadata=json_metadata,
                quiet=self.quiet,
                verbose=self.verbose,
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
