import stim
from util.erasure_converter import (
    TaskConfig,
    convert_circuit_errors_to_erasures,
    filter_convert_to_erasure_instructions,
)


def test_surface_code_layout_conversion_factor_equals_1():
    p = 0.01
    d = 3
    conversion_factor = 1
    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_x",
        rounds=d * 3,
        distance=d,
        before_round_data_depolarization=p,
    )
    task = TaskConfig(circuit=circuit, json_metadata={"p": p, "d": d})
    result = convert_circuit_errors_to_erasures(
        task, conversion_factor=conversion_factor
    )
    modified_circuit = result.circuit
    erased_errors = filter_convert_to_erasure_instructions(modified_circuit)

    # if the conversion factor is 1, we expect all depolarizing noise to have p=0 in the modified circuit
    for err in erased_errors:
        gate_args = err.gate_args_copy()
        assert gate_args[0] == 0
