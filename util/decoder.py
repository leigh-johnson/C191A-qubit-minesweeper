import stim
import sinter
import pymatching

import numpy as np
import stim


class HeraldedEraseCompiledDecoder(sinter.CompiledDecoder):
    def __init__(
        self,
        *,
        matching,
        syndrome_det_indices,
        herald_det_indices,
        edge_base_weights,
        edge_delta_weights_per_herald,
        enable_correlations: bool = True,
    ):
        self._matching = matching
        self._syn_idx = np.asarray(syndrome_det_indices, dtype=np.int64)
        self._her_idx = np.asarray(herald_det_indices, dtype=np.int64)
        self._w0 = np.asarray(edge_base_weights, dtype=float)
        self._dw = np.asarray(edge_delta_weights_per_herald, dtype=float)
        self._enable_correlations = enable_correlations

    def decode_shots_bit_packed(
        self, *, bit_packed_detection_event_data: np.ndarray
    ) -> np.ndarray:
        # bit_packed_detection_event_data:
        #   dtype: uint8
        #   shape: (num_shots, ceil(num_detectors / 8))

        if bit_packed_detection_event_data.dtype != np.uint8:
            raise ValueError("Expected uint8 bit-packed dets")

        num_shots = bit_packed_detection_event_data.shape[0]
        num_det = self._matching.num_detectors

        # 1. Unpack bytes -> bits (little-endian to match sinter contract).
        bits = np.unpackbits(
            bit_packed_detection_event_data,
            axis=1,
            bitorder="little",
        )
        # bits.shape = (num_shots, 8 * ceil(num_det / 8))
        # Trim to exactly num_det detector bits.
        det_block = bits[:, :num_det]  # shape (num_shots, num_det)

        num_obs = self._matching.num_fault_ids  # usually == dem.num_observables

        # We'll accumulate raw observable bits per shot here.
        obs_bits = np.zeros((num_shots, num_obs), dtype=np.uint8)

        for k in range(num_shots):
            # Full detection events for PyMatching.
            z = det_block[k]  # shape (num_det,)

            # Herald bits (subset of detectors).
            her = z[self._her_idx]  # shape (num_heralds,)

            # Per-edge weights for this shot:
            fired = her.astype(float)
            w = self._w0 + fired @ self._dw  # shape (num_edges,)

            # PyMatching returns a length num_fault_ids vector of 0/1 ints.
            preds = self._matching.decode(
                z,
                enable_correlations=self._enable_correlations,
                edge_weights=w,
            )
            # Ensure 0/1 uint8
            obs_bits[k, :] = np.asarray(preds, dtype=np.uint8) & 1

        # 2. Bit-pack observable bits into uint8 with bitorder='little'.
        if num_obs == 0:
            # Edge case: no observables. Sinter still wants a uint8 array
            # with width ceil(0/8) = 0, which numpy can handle.
            return np.zeros((num_shots, 0), dtype=np.uint8)

        pad = (-num_obs) % 8  # how many zeros to pad to multiple of 8
        if pad:
            padded = np.pad(obs_bits, ((0, 0), (0, pad)), mode="constant")
        else:
            padded = obs_bits

        packed = np.packbits(padded, axis=1, bitorder="little")  # uint8
        # packed.shape = (num_shots, ceil(num_obs / 8))
        return packed


import math
from typing import List, Tuple

import numpy as np
import stim
import mwpf.ref_circuit


def analyze_erasures(
    circuit: stim.Circuit,
    dem: stim.DetectorErrorModel,
    *,
    herald_alpha: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Analyze a Stim circuit that has been converted to use HERALDED_ERASE.

    Returns:
        syndrome_det_indices: 1D int array of detector indices that are "normal"
            stabilizer detectors (i.e., not herald detectors).
        herald_det_indices: 1D int array of *representative* detector indices
            (one per heralded erase event). You can still get all detectors per
            herald via internal structures if needed, but this is a useful
            compact handle.
        edge_base_weights: 1D float array of length dem.num_errors, giving the
            base log-odds weight for each DEM error:
                w_base[j] = log((1 - q_j) / q_j)
            where q_j is the DEM's error probability.
        edge_delta_weights_per_herald: 2D float array of shape
            (num_heralds, dem.num_errors). Entry [h, j] gives the extra weight
            to add to edge j when herald h fires:
                w(j | herald h = 1) = edge_base_weights[j] + edge_delta[h, j]

    Assumptions / conventions:
      * The circuit has been produced by `convert_circuit_errors_to_erasures`,
        i.e. each HERALDED_ERASE is followed immediately by one or more
        DETECTOR instructions corresponding to herald detectors for that erase.
      * All other DETECTORs are "normal" syndrome detectors.
      * We treat each DEM `error(...)` instruction as one "edge".
      * For each herald h, we treat all DEM errors that touch that herald's
        detectors as "associated" with that herald, and make them cheaper when
        the herald fires.
      * We use a simple two-level model per herald:
            p_base = q_j     (un-conditional DEM probability)
            p_herald = alpha     (configurable; default 0.5)
        so the delta weight is:
            delta_w = log((1 - p_herald)/p_herald) - log((1 - p_base)/p_base)

    You can plug these arrays into a custom sinter.CompiledDecoder that
    computes per-shot weights via:
        w = edge_base_weights + herald_bits @ edge_delta_weights_per_herald
    and then (re)builds or reuses a Matching configured with those weights.
    """

    # ----------------------------------------------------------------------
    # 1. Classify detectors: which are herald vs normal syndrome?
    # ----------------------------------------------------------------------
    ref = mwpf.ref_circuit.RefCircuit.of(circuit)

    det_index = 0
    syndrome_det_indices: List[int] = []
    # For each herald event h, we store *all* detector indices that belong to it.
    herald_det_groups: List[List[int]] = []
    # Map det_index -> herald_id (for later mapping DEM errors to heralds).
    det_to_herald = {}

    pending_herald_id = None

    for inst in ref:
        name = inst.name

        if name == "HERALDED_ERASE":
            # Start a new herald group. All subsequent DETECTOR instructions
            # belong to this herald *until* we hit a non-DETECTOR instruction.
            pending_herald_id = len(herald_det_groups)
            herald_det_groups.append([])

        elif name == "DETECTOR":
            if pending_herald_id is not None:
                # This detector belongs to the most recent HERALDED_ERASE.
                herald_det_groups[pending_herald_id].append(det_index)
                det_to_herald[det_index] = pending_herald_id
            else:
                # "Normal" surface-code detector.
                syndrome_det_indices.append(det_index)
            det_index += 1

        else:
            # Any non-detector instruction ends the run of herald detectors.
            pending_herald_id = None

    num_heralds = len(herald_det_groups)
    syndrome_det_indices = np.asarray(syndrome_det_indices, dtype=np.int64)

    # For convenience, choose ONE representative detector index per herald.
    # (You can always look back at herald_det_groups if you want to OR them.)
    herald_det_indices = np.asarray(
        [grp[0] for grp in herald_det_groups],
        dtype=np.int64,
    )

    # ----------------------------------------------------------------------
    # 2. Flatten DEM errors and collect their probabilities + detector targets
    # ----------------------------------------------------------------------
    # We need a stable indexing of "errors" (dem_error_index), consistent with
    # dem.num_errors. We also need to know which detector ids each error touches.
    #
    # Stim's DetectorErrorModel includes repeat blocks; num_errors counts each
    # repeated error once per repetition. We'll flatten repeats manually.

    error_detector_ids: List[List[int]] = []
    error_probabilities: List[float] = []

    def _walk_dem(block: stim.DetectorErrorModel, det_offset: int):
        """Recursively flatten DEM errors, tracking detector ids with global offset."""
        nonlocal error_detector_ids, error_probabilities

        cur_det_shift = det_offset

        for inst in block:
            if isinstance(inst, stim.DemRepeatBlock):
                reps = inst.repeat_count
                # Recursively expand the repeated sub-block reps times.
                for _ in range(reps):
                    body = inst.body_copy()
                    _walk_dem(body, cur_det_shift)
                    # After each repetition, apply any net detector shift that
                    # the sub-block ends with. We can approximate by using
                    # inst.body.num_detectors, which is the total range of
                    # detector ids touched by the body.
                    cur_det_shift += body.num_detectors
            else:
                # Normal DemInstruction
                if inst.type == "shift_detectors":
                    # Shift_detectors K just moves future detector ids by +K.
                    inst_args = inst.args_copy()
                    shift = int(inst_args[0])
                    cur_det_shift += shift

                elif inst.type == "error":
                    # inst.args[0] is the error probability
                    inst_args = inst.args_copy()
                    p = float(inst_args[0])
                    error_probabilities.append(p)

                    # Collect the detectors this error touches, adjusted by current shift.
                    dets_here: List[int] = []
                    targets = inst.targets_copy()
                    for t in targets:
                        if t.is_relative_detector_id():
                            dets_here.append(cur_det_shift + t.val)
                    error_detector_ids.append(dets_here)

                # We ignore other DEM instructions (logical_observable, detector, etc.)

        return cur_det_shift

    _walk_dem(dem, det_offset=0)

    num_errors = len(error_probabilities)
    assert num_errors == dem.num_errors, (
        f"Flattened {num_errors} errors but dem.num_errors={dem.num_errors}; "
        "check DEM parsing logic."
    )

    error_probabilities = np.asarray(error_probabilities, dtype=float)

    # ----------------------------------------------------------------------
    # 3. Map each error to the herald(s) whose detectors it touches
    # ----------------------------------------------------------------------
    # For each DEM error j, we check its detector ids; if any of those are
    # herald detectors, we associate error j to that herald.
    error_to_heralds: List[List[int]] = [[] for _ in range(num_errors)]

    for j, det_ids in enumerate(error_detector_ids):
        seen_heralds = set()
        for d in det_ids:
            h = det_to_herald.get(d, None)
            if h is not None:
                seen_heralds.add(h)
        error_to_heralds[j] = sorted(seen_heralds)

    # ----------------------------------------------------------------------
    # 4. Compute base weights and per-herald delta weights
    # ----------------------------------------------------------------------
    # Base weights: use the DEM's error probabilities q_j.
    #   w_base[j] = log((1 - q_j)/q_j)
    #
    # Herald model: when herald h fires for an error j associated with h, we
    # override its probability to p_herald = herald_alpha (typically 0.5).
    #   w_herald[j] = log((1 - α)/α)
    # and define
    #   delta_w[h, j] = w_herald[j] - w_base[j]
    #
    # Errors not associated with h get delta_w[h, j] = 0.

    # Avoid log(0)/division by zero for extremely small or large probabilities.
    eps = 1e-15
    q = np.clip(error_probabilities, eps, 1 - eps)

    edge_base_weights = np.log((1.0 - q) / q)

    alpha = float(herald_alpha)
    alpha = min(max(alpha, eps), 1 - eps)
    w_herald = math.log((1.0 - alpha) / alpha)

    edge_delta_weights_per_herald = np.zeros(
        (num_heralds, num_errors),
        dtype=float,
    )

    for j, herald_list in enumerate(error_to_heralds):
        if not herald_list:
            continue
        # This error is "tied" to at least one herald. Right now we give it the
        # same w_herald for all those heralds; if multiple heralds are involved,
        # you may want something more sophisticated later.
        base = edge_base_weights[j]
        delta = w_herald - base
        for h in herald_list:
            edge_delta_weights_per_herald[h, j] = delta

    return (
        syndrome_det_indices,
        herald_det_indices,
        edge_base_weights,
        edge_delta_weights_per_herald,
    )


class HeraldedEraseDecoder(sinter.Decoder):

    def __init__(self, circuit: stim.Circuit, *, enable_correlations: bool = True):
        self._circuit = circuit
        self._enable_correlations = enable_correlations

        # Precompute DEM from the converted circuit
        self._dem = circuit.detector_error_model(
            decompose_errors=True, approximate_disjoint_errors=True, flatten_loops=True
        )

        # Analyze circuit+DEM to identify:
        #  - which detector indices are "normal stabilizer" vs "herald detectors"
        #  - which DEM edges are affected when a given herald fires
        (
            self._syndrome_det_indices,
            self._herald_det_indices,
            self._edge_base_weights,
            self._edge_delta_weights_per_herald,
        ) = analyze_erasures(self._circuit, self._dem)

    def compile_decoder_for_dem(self, dem: stim.DetectorErrorModel):
        # sanity: we assume `dem` equals `self._dem`
        # (or you can skip this check if you know they always match)
        # if str(dem) != str(self._dem):
        #     raise ValueError("DEM mismatch; ensure tasks use the same converted circuit.")

        matching = pymatching.Matching.from_detector_error_model(
            dem,
            enable_correlations=self._enable_correlations,
        )

        return HeraldedEraseCompiledDecoder(
            matching=matching,
            syndrome_det_indices=self._syndrome_det_indices,
            herald_det_indices=self._herald_det_indices,
            edge_base_weights=self._edge_base_weights,
            edge_delta_weights_per_herald=self._edge_delta_weights_per_herald,
            enable_correlations=self._enable_correlations,
        )


# class CorrelatedPyMatchingCompiledDecoder(CompiledDecoder):
#     def __init__(self, matcher: "pymatching.Matching"):
#         self.matcher = matcher

#     def decode_shots_bit_packed(
#         self,
#         *,
#         bit_packed_detection_event_data: "np.ndarray",
#     ) -> "np.ndarray":
#         return self.matcher.decode_batch(
#             shots=bit_packed_detection_event_data,
#             bit_packed_shots=True,
#             bit_packed_predictions=True,
#             return_weights=False,
#             enable_corrections=True,
#         )


""" pymatching.Matcher.from_detector_error_model:
    Constructs a `pymatching.Matching` object by loading from a `stim.DetectorErrorModel`.

    A `stim.DetectorErrorModel` (DEM) describes a circuit-level noise model in a quantum error correction protocol,
    and is defined in the
    Stim documentation: https://github.com/quantumlib/Stim/blob/main/doc/file_format_dem_detector_error_model.md.
    When loading from a DEM, there is a one-to-one correspondence with a detector in the DEM and a
    node in the `pymatching.Matching` graph, and each graphlike error in the DEM becomes an edge (or merged into
    a parallel edge) in the `pymatching.Matching` graph.
    A error instruction in the DEM is graphlike if it causes either one or two detection events, and can be
    either its own DEM instruction, or within a suggested decomposition of a larger DEM instruction.
    Error instruction in the DEM that cause more than two detection events and do not have a suggested
    decomposition into edges are ignored.
    There set of `fault_ids` assigned to a `pymatching.Matching` graph edge is the set of
    `logical_observable` indices associated with the corresponding graphlike fault mechanism in the DEM.
    Parallel edges are merged, with weights chosen on the assumption that the error mechanisms associated with the
    parallel edges are independent.
    the `logical_observable` indices associated with the first added parallel edge are kept for the merged edge.
    If you are loading a `pymatching.Matching` graph from a DEM, you may be interested in
    using the sinter Python package for monte carlo sampling: https://pypi.org/project/sinter/.

"""

""""
        Constructs a `pymatching.Matching` object by loading from a `stim.Circuit`

        Parameters
        ----------
        circuit : stim.Circuit
            A stim circuit containing error mechanisms that are all either graphlike, or decomposable into
            graphlike error mechanisms
        enable_correlations : bool, optional
            If `enable_correlations==True`, the circuit's detector error model is converted into an internal
            representation that allows correlated matching to be used. Note that you must set
            `enable_correlations=True` here in order to use `enable_correlations=True` when decoding.
            By default, False.

        Returns
        -------
        pymatching.Matching
            A `pymatching.Matching` object representing the graphlike error mechanisms in `circuit`, with any hyperedge
            error mechanisms decomposed into graphlike error mechanisms. Parallel edges are merged using
            `merge_strategy="independent"`.


        Examples
        --------
        >>> import stim
        >>> import pymatching
        >>> circuit = stim.Circuit.generated("surface_code:rotated_memory_x",
        ...                                  distance=5,
        ...                                  rounds=5,
        ...                                  after_clifford_depolarization=0.005)
        >>> matching = pymatching.Matching.from_stim_circuit(circuit)
        >>> matching
        <pymatching.Matching object with 120 detectors, 0 boundary nodes, and 502 edges>
"""


# class CorrelatedPyMatchingDecoder(Decoder):
#     def compile_decoder_for_dem(
#         self, *, dem: "stim.DetectorErrorModel"
#     ) -> CorrelatedPyMatchingCompiledDecoder:
#         try:
#             import pymatching
#         except ImportError as ex:
#             raise ImportError(
#                 "The decoder 'pymatching' isn't installed\n"
#                 "To fix this, install the python package 'pymatching' into your environment.\n"
#                 "For example, if you are using pip, run `pip install pymatching`.\n"
#             ) from ex

#         return CorrelatedPyMatchingCompiledDecoder(
#             pymatching.Matching.from_detector_error_model(dem, enable_correlations=True)
#         )
