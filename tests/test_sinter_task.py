from util.sinter_task import (
    generate_save_resume_filepath,
    CollectTasksConfig,
    DecoderLib,
    MWPFSolverType,
)
from datetime import date
from pathlib import Path


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
