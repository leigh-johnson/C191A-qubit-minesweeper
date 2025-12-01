import dataclasses
from types import SimpleNamespace

import numpy as np
import pytest
import stim
import sinter

from util.decoder import analyze_erasures
from util.sinter_task import TaskConfig, DecoderLib
from util.erasure_converter import convert_task_config_to_erasures


def make_rotated_memory_task(d: int = 5, p: float = 0.01) -> TaskConfig:
    """Helper to build the reference surface code memory circuit used in tests."""
    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_x",
        rounds=d * 3,
        distance=d,
        before_round_data_depolarization=p,
        after_clifford_depolarization=p,
        after_reset_flip_probability=p,
        before_measure_flip_probability=p,
    )
    meta = SimpleNamespace(
        d=d,
        p=p,
        label="rotated_memory_x",
        decoder=DecoderLib.PYMATCHING_CORRELATED,
        decoder_type=None,
        cluster_node_limit=None,
    )
    return TaskConfig(circuit=circuit, json_metadata=meta, quiet=False)


def convert_task_circuit(
    task_cfg: TaskConfig, conversion_factor: float
) -> stim.Circuit:
    """Apply your Pauli→HERALDED_ERASE conversion and return the converted circuit."""
    new_cfg = convert_task_config_to_erasures(
        task_config=task_cfg,
        conversion_factor=conversion_factor,
        add_detectors=True,
    )
    return new_cfg.circuit


@pytest.mark.parametrize("conversion_factor", [1.0, 0.5])
def test_analyze_erasures_basic_properties(conversion_factor):
    task = make_rotated_memory_task(d=5, p=0.01)
    converted_circuit = convert_task_circuit(task, conversion_factor)

    dem = converted_circuit.detector_error_model(
        decompose_errors=True, approximate_disjoint_errors=True, flatten_loops=True
    )

    (
        syndrome_det_indices,
        herald_det_indices,
        edge_base_weights,
        edge_delta_weights_per_herald,
    ) = analyze_erasures(converted_circuit, dem, herald_alpha=0.5)

    # Basic shape checks
    assert syndrome_det_indices.ndim == 1
    assert herald_det_indices.ndim == 1
    assert edge_base_weights.ndim == 1
    assert edge_delta_weights_per_herald.ndim == 2

    num_heralds, num_errors = edge_delta_weights_per_herald.shape
    assert num_errors == dem.num_errors
    assert herald_det_indices.size == num_heralds

    # We expect at least one herald detector to exist after conversion.
    assert num_heralds > 0

    # Some edges should actually be tied to heralds, meaning at least one
    # delta weight is non-zero.
    assert np.any(edge_delta_weights_per_herald != 0.0)

    # Base weights should be finite and non-trivial.
    assert np.all(np.isfinite(edge_base_weights))
    assert np.any(edge_base_weights != 0.0)


def test_analyze_erasures_full_vs_half_conversion_differs():
    """Check that full vs half conversion produce different base weights,
    i.e. that the DEM actually changed and analyze_erasures is sensitive to it.
    """
    task = make_rotated_memory_task(d=5, p=0.01)

    circuit_full = convert_task_circuit(task, 1.0)
    dem_full = circuit_full.detector_error_model(
        decompose_errors=True, approximate_disjoint_errors=True, flatten_loops=True
    )
    _, _, base_full, delta_full = analyze_erasures(
        circuit_full, dem_full, herald_alpha=1
    )

    circuit_half = convert_task_circuit(task, 0.5)
    dem_half = circuit_half.detector_error_model(
        decompose_errors=True, approximate_disjoint_errors=True, flatten_loops=True
    )
    _, _, base_half, delta_half = analyze_erasures(
        circuit_half, dem_half, herald_alpha=1
    )

    # Expect dem_full to contain fewer errors, since we replaced some error instructions with HERALDED_ERASE instructions
    assert dem_full.num_errors < dem_half.num_errors
    # At least one base weight should differ
    assert not np.allclose(base_full, base_half[base_full.shape[0]])
