import stim
import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Optional, Dict
from tqdm import tqdm
from datetime import datetime, timezone, date
from enum import StrEnum

import sinter
from mwpf import SinterMWPFDecoder


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


def build_custom_decoders(cfg: TaskConfig, with_progress: bool = True):
    return {
        f"mwpf__{cfg.run_id}": SinterMWPFDecoder(
            decoder_type="SolverSerialJointSingleHair",
            cluster_node_limit=cfg.json_metadata.cluster_node_limit,
            with_progress=with_progress,
            timeout=10,
        ).with_circuit(cfg.circuit)
    }
