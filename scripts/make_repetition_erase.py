import stim
import os
from util.param_parser import parse_stim_generated_header

indir = "circuits/repetition/baseline/"
outdir = "circuits/repetition/erase/"
# add erasure noise before the following operations (on data qubits)
GATESET = ("CX", "H", "X", "Z", "M", "R")


# TODO - it'd be nice to output file fixtures of our erassure-converted circuitry (similar to the baseline circuits).
# right now, the erasure conversion process is only implemented in mwpf_demo.ipynb
for filename in os.listdir(indir):
    inpath = os.path.join(indir, filename)
    circuit = stim.Circuit.from_file(inpath)
    # turn off Pauli noise, but keep the rest of the circuit specs so we can repeat the parameter sweep
    # TODO - parameterize ratio of Pauli : erasure noise
    noiseless_circuit = circuit.without_noise()
    with open(inpath) as file:
        parsed_params = parse_stim_generated_header(file.read())
    import pdb; pdb.set_trace()
    # assume
    data_qubits = list(range(parsed_params.d))
    for op in circuit:
        if op in GATESET:
            # TODO
            # circuit.append("HERALDED_ERASE", data_qubits, erase_prob)
