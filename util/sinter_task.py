import stim
import hashlib
import json
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List, Union
from enum import StrEnum

import sinter
from mwpf import SinterMWPFDecoder, PanicAction
from mwpf import __version__ as mwpf_version

from util.decoder import HeraldedEraseDecoder


class DecoderLib(StrEnum):
    PYMATCHING_CORRELATED = "HeraldedEraseDecoder"  # included in task metadata
    PYMATCHING = "pymatching"  # sinter expects to match on this string
    MWPF = "SinterMWPFDecoder"  # included in task metadata

    def __str__(self):
        return self.value


# sinter.collect has a slightly different fn signature for custom decoders
CUSTOM_DECODERS = (DecoderLib.MWPF, DecoderLib.PYMATCHING_CORRELATED)


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
    p_erase: float = 0.0
    stim_version: str = stim.__version__
    sinter_version: str = sinter.__version__
    cluster_node_limit: Optional[int] = None

    def __post_init__(self):
        if self.decoder is DecoderLib.MWPF:
            self.decoder_version = mwpf_version
        elif self.decoder is DecoderLib.PYMATCHING_CORRELATED:
            self.decoder_version = HeraldedEraseDecoder.__version__


@dataclass
class TaskConfig:
    circuit: stim.Circuit
    json_metadata: TaskMetadata
    custom_decoders: Optional[
        Union[Dict[str, SinterMWPFDecoder], Dict[str, HeraldedEraseDecoder]]
    ] = None
    quiet: bool = False
    verbose: bool = False
    heralded_detector_indices: List[int] = field(default_factory=list)

    def __post_init__(self):
        if self.json_metadata.decoder in CUSTOM_DECODERS:
            self.custom_decoders = build_custom_decoders(
                self, with_progress=not self.quiet
            )
        self.json_metadata.run_id = self.run_id

    @property
    def run_id(self):
        return id(self.circuit)

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
        elif self.json_metadata.decoder is DecoderLib.PYMATCHING_CORRELATED:
            return sinter.Task(
                circuit=self.circuit,
                json_metadata=asdict(self.json_metadata),
                decoder=list(self.custom_decoders)[0],
            )
        else:
            raise NotImplementedError(
                "TaskConfig.to_task not implemented for", self.json_metadata.decoder
            )


def build_mwpf_custom_decoder(cfg: TaskConfig, with_progress: bool = True):
    if cfg.verbose:
        panic_action = PanicAction.RAISE
    else:
        panic_action = PanicAction.CATCH
    return {
        f"{cfg.json_metadata.decoder}.{cfg.run_id}": SinterMWPFDecoder(
            decoder_type=cfg.json_metadata.decoder_type,
            cluster_node_limit=cfg.json_metadata.cluster_node_limit,
            with_progress=with_progress,
            panic_action=panic_action,
        ).with_circuit(cfg.circuit)
    }


def build_pymatching_custom_decoder(cfg: TaskConfig):
    return {
        f"{cfg.json_metadata.decoder}.{cfg.run_id}": HeraldedEraseDecoder(cfg.circuit)
    }


def build_custom_decoders(cfg: TaskConfig, with_progress: bool = True):
    if cfg.json_metadata.decoder is DecoderLib.MWPF:
        return build_mwpf_custom_decoder(cfg, with_progress=with_progress)
    elif cfg.json_metadata.decoder is DecoderLib.PYMATCHING_CORRELATED:
        return build_pymatching_custom_decoder(cfg)
    else:
        raise NotImplementedError(
            "build_custom_decoders not implemented for", cfg.json_metadata.decoder
        )
