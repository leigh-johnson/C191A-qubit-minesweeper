import click
from dataclasses import dataclass
from typing import Optional
import os
from util.sinter_task import (
    MWPFSolverType,
    DecoderLib,
)
from util.sinter_collect import CollectTasksConfig, collect_stats


@dataclass
class CommonOpts:
    circuit: str
    max_errors: int
    max_shots: int
    noise: tuple[float, ...]
    code_distance: tuple[int, ...]
    save_resume_filepath: str
    quiet: bool = False
    num_workers: int = os.cpu_count() - 2
    num_rounds: Optional[int] = None
    verbose: bool = False
    max_batch_size: int = 1024


def common_options(f):
    f = click.option(
        "--max-batch-size",
        "max_batch_size",
        type=int,
        default=1024,
        show_default=True,
        help="Max sinter batch size",
    )(f)
    f = click.option(
        "--num-workers",
        "num_workers",
        type=int,
        default=os.cpu_count() - 2,
        show_default=True,
        help="Number of sinter (multiprocessing) workers. NOTE: sinter uses spawn (not fork) to create subprocesses, so each additional worker process adds cold start time sinter.collect() calls. Prefer a high number of worker processes with few (ideally one) call to sinter.collect().",
    )(f)
    f = click.option(
        "--num-rounds",
        "num_rounds",
        type=int,
        help="Number of rounds per circuit. Repeated rounds are needed when measurement error is nonzero. Default: 3*d (code distance) to allow a majority-rules determination of stabilizer measurements.",
    )(f)
    f = click.option(
        "--code-distance",
        "code_distance",
        type=int,
        multiple=True,
        default=(3, 5, 7, 9, 11, 13),
        show_default=True,
        help="Repeatable. Example: --code-distance 3 --code-distance 5",
    )(f)
    f = click.option(
        "--noise",
        type=float,
        multiple=True,
        default=(
            0.003,
            0.004,
            0.005,
            0.006,
            0.0065,
            0.007,
            0.0075,
            0.008,
            0.009,
            0.01,
            0.015,
        ),
        show_default=True,
        help="Repeatable. Example: --noise 0.01 --noise 0.02",
    )(f)
    f = click.option(
        "--max-shots",
        default=100_000,
        show_default=True,
        help="Max number of shots (trials) in Monte Carlo simulation.",
    )(f)
    f = click.option(
        "--max-errors",
        default=5_000,
        show_default=True,
        help="Max number of errors in Monte Carlo simulator shots.",
    )(f)
    f = click.option(
        "--circuit",
        type=click.Choice(["surface_code:rotated_memory_x"]),
        default="surface_code:rotated_memory_x",
        show_default=True,
    )(f)
    f = click.option("--quiet", is_flag=True, default=False, help="Silence progress")(f)
    f = click.option(
        "--verbose", is_flag=True, default=False, help="Enable verbose logging"
    )(f)
    f = click.option(
        "--save-resume-filepath",
        default="auto",
        help="Specify a save/resume filepath to pass to sinter.collect. If 'auto', a path will be generated from dataset parameters",
    )(f)
    # TODO
    # f = click.option(
    #     "--fanout",
    #     is_flag=True,
    #     default=False,
    #     help="If true, fanout sinter.collect() and resulting dataset files (typically per unique pair of (d, p) parameters). Fanout is needed for mwpf w/ erasure enabled, so the save/resume checkpoints are more granular. For other decoders (pymatching), fanout is generally not needed and is slower, so specify only if you.  want to generate granular dataset files)",
    # )(f)
    return f


@click.group()
@common_options
@click.pass_context
def cli(
    ctx,
    max_batch_size,
    num_workers,
    num_rounds,
    circuit,
    max_errors,
    max_shots,
    noise,
    code_distance,
    save_resume_filepath,
    quiet,
    verbose,
):
    ctx.ensure_object(dict)
    ctx.obj["common"] = CommonOpts(
        circuit=circuit,
        max_errors=max_errors,
        max_shots=max_shots,
        noise=noise,
        code_distance=code_distance,
        quiet=quiet,
        save_resume_filepath=save_resume_filepath,
        num_workers=num_workers,
        num_rounds=num_rounds,
        verbose=verbose,
        max_batch_size=max_batch_size,
    )


@click.option(
    "--erasure-conversion-factor",
    default=0.0,
    show_default=True,
    help="Convert % of Pauli errors to erasures. 0 implies no conversion (default), 1 implies 100% conversion.",
)
@click.command()
@click.pass_context
def pymatching(ctx, erasure_conversion_factor):
    common: CommonOpts = ctx.obj["common"]
    assert erasure_conversion_factor >= 0 and erasure_conversion_factor <= 1
    if erasure_conversion_factor != 0.0 and erasure_conversion_factor != 1.0:
        raise NotImplementedError
    if erasure_conversion_factor == 0:
        decoder = DecoderLib.PYMATCHING
    else:
        decoder = DecoderLib.PYMATCHING_CORRELATED
    cfg = CollectTasksConfig(
        circuit=common.circuit,
        save_resume_filepath=common.save_resume_filepath,
        decoder=decoder,
        max_shots=common.max_shots,
        max_errors=common.max_errors,
        num_workers=common.num_workers,
        erasure_conversion_factor=erasure_conversion_factor,
        noise=common.noise,
        code_distance=common.code_distance,
        verbose=common.verbose,
        num_rounds=common.num_rounds,
    )
    collect_stats(cfg)
    # TODO: write CollectTasksConfig (serialized to JSON) to {save_resume_filepath}vars.json"


@click.option(
    "--cluster-node-limit",
    default=50,
    show_default=True,
    help="Hyperblossom decomposes a hypergraph problem into smaller, localized clusters. c=0 implies the UnionFind strategy, while any c >=1 will use the SerialJointSingleHair strategy. See description of c= parameter in https://arxiv.org/pdf/2508.04969",
)
@click.option(
    "--erasure-conversion-factor",
    default=0.0,
    show_default=True,
    help="Convert % of Pauli errors to erasures. 0 implies no conversion (default), 1 implies 100% conversion.",
)
@click.option(
    "--solver",
    type=click.Choice(MWPFSolverType),
    default=MWPFSolverType.SolverSerialJointSingleHair,
    show_default=True,
    help="See: https://github.com/yuewuo/mwpf/blob/main/src/mwpf_solver.rs",
)
@click.command()
@click.pass_context
def mwpf(ctx, cluster_node_limit, erasure_conversion_factor, solver):
    common: CommonOpts = ctx.obj["common"]
    assert erasure_conversion_factor >= 0 and erasure_conversion_factor <= 1
    if erasure_conversion_factor != 0 and erasure_conversion_factor != 1:
        raise NotImplementedError
    cfg = CollectTasksConfig(
        circuit=common.circuit,
        save_resume_filepath=common.save_resume_filepath,
        decoder=DecoderLib.MWPF,
        decoder_type=solver,
        max_shots=common.max_shots,
        max_errors=common.max_errors,
        num_workers=common.num_workers,
        noise=common.noise,
        code_distance=common.code_distance,
        cluster_node_limit=cluster_node_limit,
        erasure_conversion_factor=erasure_conversion_factor,
        verbose=common.verbose,
        num_rounds=common.num_rounds,
    )
    collect_stats(cfg)


cli.add_command(pymatching)
cli.add_command(mwpf)


if __name__ == "__main__":
    cli()
