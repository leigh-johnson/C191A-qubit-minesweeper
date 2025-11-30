# test_convert_circuit_errors_to_erasures_v2.py

import math
from types import SimpleNamespace

import numpy as np
import pytest
import stim

from util.erasure_converter import (
    TaskConfig,
    convert_circuit_errors_to_erasures_v2,
    convert_task_config_to_erasures,
)
from util.sinter_task import DecoderLib


def make_simple_task_config() -> TaskConfig:
    """Create a tiny circuit with two DEPOLARIZE1 noise locations."""
    circuit = stim.Circuit(
        """
        QUBIT_COORDS(0,0) 0
        DEPOLARIZE1(0.01) 0
        M 0
        DEPOLARIZE1(0.02) 0
        M 0
        """
    )
    meta = SimpleNamespace(
        decoder=DecoderLib.PYMATCHING_CORRELATED, p=0.01
    )  # so we can setattr(p_erase, herald_detectors, etc.)
    return TaskConfig(circuit=circuit, json_metadata=meta, quiet=False)


def extract_noise_ops(circuit: stim.Circuit):
    """Return a list of (name, p) for DEPOLARIZE1/HERALDED_ERASE in the circuit."""
    out = []
    for inst in circuit:
        if isinstance(inst, stim.CircuitRepeatBlock):
            # For these tests we aren't using repeat blocks.
            continue
        if inst.name in ("DEPOLARIZE1", "HERALDED_ERASE"):
            gate_args = inst.gate_args_copy()
            assert gate_args, f"{inst.name} must have a probability gate arg"
            p = float(gate_args[0])
            out.append((inst.name, p))
    return out


def extract_detector_indices_for_heralds(circuit: stim.Circuit):
    """Scan the circuit and record detector indices immediately after HERALDED_ERASE."""
    herald_detector_indices = []
    det_index = 0
    prev_name = None

    for inst in circuit:
        if isinstance(inst, stim.CircuitRepeatBlock):
            # For this simple test we ignore repeat blocks.
            continue

        name = inst.name

        if name == "DETECTOR":
            if prev_name == "HERALDED_ERASE":
                herald_detector_indices.append(det_index)
            det_index += 1

        prev_name = name

    return herald_detector_indices


# ---------------------------------------------------------------------------
# 1. 100% conversion: no DEPOLARIZE1 remains, one DETECTOR per HERALDED_ERASE
# ---------------------------------------------------------------------------


def test_convert_circuit_errors_to_erasures_v2_full_conversion():
    task = make_simple_task_config()
    conv_factor = 1.0

    converted = convert_task_config_to_erasures(
        task_config=task,
        conversion_factor=conv_factor,
        add_detectors=True,
    )

    new_circ = converted.circuit

    # 1) No DEPOLARIZE1 instructions should remain.
    for inst in new_circ:
        if isinstance(inst, stim.CircuitRepeatBlock):
            continue
        assert inst.name != "DEPOLARIZE1"

    # 2) There should be HERALDED_ERASE instructions instead.
    noise_ops = extract_noise_ops(new_circ)
    names = [n for n, _ in noise_ops]
    assert names.count("HERALDED_ERASE") == 2  # we had 2 DEPOLARIZE1 originally
    assert "DEPOLARIZE1" not in names

    # 3) Each HERALDED_ERASE should have a DETECTOR immediately after it.
    herald_idxs_scan = extract_detector_indices_for_heralds(new_circ)
    assert len(herald_idxs_scan) == 2

    # 4) The function should track herald_detector_indices and mirror them into metadata.
    assert converted.circuit.heralded_detector_indices == herald_idxs_scan
    # 5) p_erase in metadata should be conversion_factor * last p (0.02 in this circuit).
    # TODO - conversion_factor < 1
    # assert math.isclose(converted.json_metadata.p_erase, conv_factor * 0.02)


# ---------------------------------------------------------------------------
# 2. 50% conversion: residual DEPOLARIZE1 + HERALDED_ERASE with correct probs
# ---------------------------------------------------------------------------


def test_convert_circuit_errors_to_erasures_v2_half_conversion():
    task = make_simple_task_config()
    conv_factor = 0.5

    converted = convert_task_config_to_erasures(
        task_config=task,
        conversion_factor=conv_factor,
        add_detectors=True,
    )

    new_circ = converted.circuit

    # Extract noise operations in order
    noise_ops = extract_noise_ops(new_circ)
    names = [n for n, _ in noise_ops]
    probs = [p for _, p in noise_ops]

    # We had 2 original DEPOLARIZE1s, each should now become:
    #   DEPOLARIZE1(p * (1 - conv_factor)) + HERALDED_ERASE(4/3 * p * conv_factor)
    # in the same order.
    assert names == [
        "DEPOLARIZE1",
        "HERALDED_ERASE",
        "DEPOLARIZE1",
        "HERALDED_ERASE",
    ]

    p1, p2 = 0.01, 0.02

    expected_residual = [
        p1 * (1.0 - conv_factor),
        p2 * (1.0 - conv_factor),
    ]
    expected_erase = [
        min(1.0, (4.0 / 3.0) * p1 * conv_factor),
        min(1.0, (4.0 / 3.0) * p2 * conv_factor),
    ]

    residual_probs = [probs[0], probs[2]]
    erase_probs = [probs[1], probs[3]]

    assert np.allclose(residual_probs, expected_residual, rtol=1e-6, atol=1e-12)
    assert np.allclose(erase_probs, expected_erase, rtol=1e-6, atol=1e-12)

    # 1) There should still be herald detectors, one per HERALDED_ERASE.
    herald_idxs_scan = extract_detector_indices_for_heralds(new_circ)
    assert len(herald_idxs_scan) == 2

    assert converted.circuit.heralded_detector_indices == herald_idxs_scan
    # 2) p_erase in metadata uses the last original p (=0.02)
    # TODO - conversion_factor < 1
    # assert math.isclose(converted.json_metadata.p_erase, conv_factor * 0.02)


# ---------------------------------------------------------------------------
# 3. No-detector mode: add_detectors=False should not add herald detectors
# ---------------------------------------------------------------------------


def test_convert_circuit_errors_to_erasures_v2_without_detectors():
    task = make_simple_task_config()

    converted = convert_task_config_to_erasures(
        task_config=task,
        conversion_factor=1.0,
        add_detectors=False,
    )

    new_circ = converted.circuit

    # There should be HERALDED_ERASE gates but *no* DETECTOR instructions
    has_heralded = False
    num_detectors = 0
    for inst in new_circ:
        if isinstance(inst, stim.CircuitRepeatBlock):
            continue
        if inst.name == "HERALDED_ERASE":
            has_heralded = True
        if inst.name == "DETECTOR":
            num_detectors += 1

    assert has_heralded
    assert num_detectors == 0

    # herald_detector_indices should be empty.
    assert converted.circuit.heralded_detector_indices == []
