import stim

noise = [0.01, 0.05, 0.08, 0.1, 0.2, 0.3, 0.4, 0.5]
code_distance = [3, 5, 7, 9]
outdir = "circuits/repetition/baseline/"

# goofy way to parameterize Stim CLI.
# We could generate the same circuit via Python API, e.g. 
    # stim.Circuit.generated(
    #         "repetition_code:memory",
    #         rounds=d * 3,
    #         distance=d,
    #         before_round_data_depolarization=p,
    #     ),
    #     json_metadata={'d': d, 'p': p},
    # )
# 
# Howeever, only the CLI-generated circuit contains metadata in the preamble, e.g.
    # Generated repetition_code circuit.
    # task: memory
    # rounds: 25
    # distance: 3
    # before_round_data_depolarization: 0.005
    # before_measure_flip_probability: 0.002
    # after_reset_flip_probability: 0.001
    # after_clifford_depolarization: 0.001
    # layout:
    # L0 Z1 d2 Z3 d4
    # Legend:
    #     d# = data qubit
    #     L# = data qubit with logical observable crossing
    #     Z# = measurement qubit

for d in code_distance:
    for p in noise:
        r = 3*d
        path = f"{outdir}repetition_code__d={d}_r={r}_before_round_data_depolarization={p}.stim"
        return_code = stim.main(command_line_args=[
            "gen",
            "--code=repetition_code",
            "--task=memory",
            f"--rounds={r}",
            f"--distance={d}",
            f"--before_round_data_depolarization={p}",
            "--out",
            path
        ])
        print(f"Generated {path}")
