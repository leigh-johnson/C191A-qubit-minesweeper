import stim
from util.erasure_converter import (
    convert_circuit_errors_to_erasures_v1,
    filter_convert_to_erasure_instructions,
)
from util.sinter_task import TaskMetadata, DecoderLib, TaskConfig


def test_surface_code_layout_conversion_factor_equals_1():
    p = 0.01
    d = 3
    r = d * 3
    conversion_factor = 1
    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_x",
        rounds=r,
        distance=d,
        before_round_data_depolarization=p,
    )
    metadata = TaskMetadata(
        p=p, d=d, r=r, circuit="surface_code:rotated_memory_x", decoder=DecoderLib.MWPF
    )
    task = TaskConfig(circuit=circuit, json_metadata=metadata)
    result = convert_circuit_errors_to_erasures_v1(
        task, conversion_factor=conversion_factor
    )
    modified_circuit = result.circuit
    erased_errors = filter_convert_to_erasure_instructions(modified_circuit)

    # if the conversion factor is 1, we expect all depolarizing noise to have p=0 in the modified circuit
    for err in erased_errors:
        gate_args = err.gate_args_copy()
        assert gate_args[0] == 0
