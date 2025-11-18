from util.param_parser import parse_stim_generated_header


def test_circuit_param_parser():
    fixture = "circuits/repetition/baseline/repetition_code__d=3_r=9_before_round_data_depolarization=0.1.stim"
    with open(fixture) as file:
        spec = file.read()
        params = parse_stim_generated_header(spec)
        assert params.distance == 3
        assert params.rounds == 9
        assert params.before_round_data_depolarization == 0.1