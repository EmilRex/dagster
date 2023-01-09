import os
import subprocess
import sys
import time
import warnings

import click

from dagster._cli.job import apply_click_params
from dagster._cli.workspace.cli_target import (
    get_workspace_load_target,
    python_file_option,
    python_module_option,
    workspace_option,
)
from dagster._core.instance import DagsterInstance
from dagster._serdes import serialize_dagster_namedtuple


def start_command_options(f):
    return apply_click_params(
        f,
        workspace_option(),
        python_file_option(),
        python_module_option(),
    )


@click.command(
    name="start",
    help=(
        "Start a local deployment of Dagster, including dagit running on localhost and the"
        " dagster-daemon running in the background"
    ),
)
@start_command_options
@click.option(
    "--grpc-log-level",
    help="Set the log level for code servers spun up by dagster services.",
    show_default=True,
    default="warning",
    type=click.Choice(
        ["critical", "error", "warning", "info", "debug", "trace"], case_sensitive=False
    ),
)
def start_command(grpc_log_level, **kwargs):
    try:
        import dagit  #  # noqa: F401
    except ImportError:
        raise click.UsageError(
            "The dagit package must be installed in order to use the dagster start command."
        )

    get_workspace_load_target(kwargs)

    dagster_home_path = os.getenv("DAGSTER_HOME")
    if not dagster_home_path:
        dagster_home_path = os.getcwd()
        warnings.warn(
            f"Using the current folder {dagster_home_path} as the folder for your Dagster storage."
            " If you run this command again from a different folder you will not have access to"
            " your runs. You can set the DAGSTER_HOME environment variable to a folder to set the"
            " permanent home for Dagster storage."
        )

    # check if dagit installed, crash if not
    with DagsterInstance.from_config(dagster_home_path) as instance:
        # Sanity check workspace args

        click.echo("Launching Dagster services...")

        args = (
            [
                "--instance-ref",
                serialize_dagster_namedtuple(instance.get_ref()),
                "--grpc-log-level",
                grpc_log_level,
            ]
            + (["--workspace", kwargs["workspace"]] if kwargs.get("workspace") else [])
            + (["--python-file", kwargs["python_file"]] if kwargs.get("python_file") else [])
            + (["--module-file", kwargs["module_file"]] if kwargs.get("module_file") else [])
        )

        try:
            dagit_process = subprocess.Popen([sys.executable, "-m", "dagit"] + args)
            daemon_process = subprocess.Popen(
                [sys.executable, "-m", "dagster._daemon", "run"] + args
            )

            while True:
                time.sleep(5)

                if dagit_process.poll() is not None:
                    raise Exception(
                        "Dagit process shut down unexpectedly with return code"
                        f" {dagit_process.returncode}"
                    )

                if daemon_process.poll() is not None:
                    raise Exception(
                        "dagster-daemon process shut down unexpectedly with return code"
                        f" {daemon_process.returncode}"
                    )

        finally:
            click.echo("Shutting down Dagster services...")

            dagit_process.terminate()
            daemon_process.terminate()
            try:
                click.echo("Waiting for dagit process to shut down...")
                dagit_process.wait(timeout=60)
                click.echo("Shut down dagit process.")
            except subprocess.TimeoutExpired:
                click.echo("dagit process did not terminate cleanly, killing the process")
                dagit_process.kill()

            try:
                click.echo("Waiting for dagster-daemon process to shut down...")
                daemon_process.wait(timeout=60)
                click.echo("Shut down dagster-daemon process.")
            except subprocess.TimeoutExpired:
                click.echo("dagster-daemon process did not terminate cleanly, killing the process")
                daemon_process.kill()
