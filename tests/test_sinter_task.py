from util.sinter_task import (
    DecoderLib,
    MWPFSolverType,
)
from util.sinter_collect import generate_save_resume_filepath, CollectTasksConfig
from util.sinter_task import TaskMetadata, DecoderLib, MWPFSolverType
from datetime import date
from pathlib import Path
from mwpf import SinterMWPFDecoder, PanicAction, __version__ as mwpf_version


def test_sinter_metadata():
    metadata = TaskMetadata(
        p=0.01,
        d=3,
        r=3,
        circuit="",
        decoder=DecoderLib.MWPF,
        decoder_type=MWPFSolverType.SolverSerialJointSingleHair,
    )
    assert metadata.decoder_version == mwpf_version


def test_generate_save_resume_filepath_pymatching():

    cfg = CollectTasksConfig(
        "surface_code:rotated_memory_x",
        decoder=DecoderLib.PYMATCHING,
        noise=[],
        code_distance=[],
    )
    assert generate_save_resume_filepath(cfg) == Path(
        "datasets/circuit=surface_code:rotated_memory_x/decoder=pymatching/"
        + date.today().isoformat()
        + ".csv"
    )


def test_generate_save_resume_filepath_mwpf():

    cfg = CollectTasksConfig(
        "surface_code:rotated_memory_x",
        decoder=DecoderLib.MWPF,
        decoder_type=MWPFSolverType.SolverSerialJointSingleHair,
        noise=[],
        code_distance=[],
    )
    assert generate_save_resume_filepath(cfg) == Path(
        "datasets/circuit=surface_code:rotated_memory_x/decoder=mwpf/erasure=0.0/solver=SolverSerialJointSingleHair/"
        + date.today().isoformat()
        + ".csv"
    )


def test_generate_task_num_rounds():
    cfg = CollectTasksConfig(
        "surface_code:rotated_memory_x",
        decoder=DecoderLib.PYMATCHING,
        noise=[0.01],
        code_distance=[3],
        num_rounds=1,
    )
    for task in cfg.tasks:
        assert task.json_metadata.get("r") == 1
