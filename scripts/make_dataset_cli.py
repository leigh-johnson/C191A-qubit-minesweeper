import click
from datetime import datetime, timezone
from dataclasses import dataclass

now_utc = datetime.now(timezone.utc)
iso_now = now_utc.isoformat(timespec="hours")


@dataclass
class CommonOpts:
    progress: bool
    circuit: str
    max_errors: int
    max_shots: int
    noise: tuple[float, ...]
    code_distance: tuple[int, ...]


def common_options(f):
    f = click.option(
        "--code-distance",
        "code_distance",
        type=int,
        multiple=True,
        default=(3, 5, 7, 9, 11, 13, 15),
        show_default=True,
        help="Repeatable. Example: --code-distance 3 --code-distance 5",
    )(f)
    f = click.option(
        "--noise",
        type=float,
        multiple=True,
        default=(
            0.001,
            0.004,
            0.005,
            0.006,
            0.0065,
            0.007,
            0.0075,
            0.008,
            0.009,
            0.01,
            0.011,
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
        type=click.Choice(["rotated_memory_x"]),
        default="rotated_memory_x",
        show_default=True,
    )(f)
    f = click.option("--progress", is_flag=True, help="Silence progress")(f)
    return f


@click.group()
@common_options
@click.pass_context
def cli(ctx, progress, circuit, max_errors, max_shots, noise, code_distance):
    ctx.ensure_object(dict)
    ctx.obj["common"] = CommonOpts(
        progress=progress,
        circuit=circuit,
        max_errors=max_errors,
        max_shots=max_shots,
        noise=noise,
        code_distance=code_distance,
    )


@click.option(
    "--folder",
    show_default=True,
    default=f"datasets/rotated_memory_x_pymatching/{iso_now}",
)
@click.command()
def pymatching():
    pass


@click.option(
    "--cluster_node_limit",
    default=50,
    show_default=True,
    help="Hyperblossom decomposes a hypergraph problem into smaller, localized clusters. c=0 implies the UnionFind strategy, while any c >=1 will use the SerialJointSingleHair strategy. See description of c= parameter in https://arxiv.org/pdf/2508.04969",
)
@click.option(
    "--folder",
    show_default=True,
    default=f"datasets/rotated_memory_x_mwpf_SolverSerialJointSingleHair/{iso_now}",
)
@click.command()
def mwpf(folder, cluster_node_limit):
    pass


@click.option(
    "--cluster_node_limit",
    default=50,
    show_default=True,
    help="Hyperblossom decomposes a hypergraph problem into smaller, \
        localized clusters. c=0 implies the UnionFind strategy, \
        while any c >=1 will use the SerialJointSingleHair strategy. \
        See description of c= parameter in https://arxiv.org/pdf/2508.04969",
)
@click.option(
    "--folder",
    show_default=True,
    default=f"datasets/rotated_memory_x_mwpf_SolverSerialJointSingleHair_erasure/{iso_now}",
)
@click.command()
def mwpf_erasure():
    pass


cli.add_command(pymatching)
cli.add_command(mwpf)
cli.add_command(mwpf_erasure)


if __name__ == "__main__":
    cli()
