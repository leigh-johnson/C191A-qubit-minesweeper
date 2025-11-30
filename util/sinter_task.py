import stim
import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Optional, Dict
from enum import StrEnum

import sinter
from pymatching import __version__ as pymatching_version
from mwpf import SinterMWPFDecoder, PanicAction, __version__ as mwpf_version


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
    decoder_version: str = ""
    run_id: str = ""
    cluster_node_limit: Optional[int] = None
    p_erase: float = 0.0
    stim_version: str = stim.__version__
    sinter_version: str = sinter.__version__

    def __post_init__(self):
        self.run_id = hashlib.sha256(
            json.dumps(asdict(self)).encode("utf-8")
        ).hexdigest()
        if self.decoder is DecoderLib.MWPF:
            self.decoder_version = mwpf_version
        elif self.decoder_type is DecoderLib.PYMATCHING:
            self.decoder_version = pymatching_version


@dataclass
class TaskConfig:
    circuit: stim.Circuit
    json_metadata: TaskMetadata
    custom_decoders: Optional[Dict[str, SinterMWPFDecoder]] = None
    quiet: bool = False
    verbose: bool = False

    def __post_init__(self):
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
        elif self.json_metadata.decoder is DecoderLib.MWPF:
            return sinter.Task(
                circuit=self.circuit,
                json_metadata=asdict(self.json_metadata),
                decoder=list(self.custom_decoders)[0],
            )
        else:
            raise NotImplemented


def build_custom_decoders(cfg: TaskConfig, with_progress: bool = True):
    if cfg.verbose:
        panic_action = PanicAction.RAISE
    else:
        panic_action = PanicAction.CATCH
    return {
        f"mwpf__{cfg.run_id}": SinterMWPFDecoder(
            decoder_type=cfg.json_metadata.decoder_type,
            cluster_node_limit=cfg.json_metadata.cluster_node_limit,
            with_progress=with_progress,
            panic_action=panic_action,
        ).with_circuit(cfg.circuit)
    }
