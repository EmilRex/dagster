from dagster import check
from dagster.core.events import EngineEventData
from dagster.core.instance import DagsterInstance
from dagster.core.instance.ref import InstanceRef
from dagster.core.origin import PipelineGrpcServerOrigin, PipelinePythonOrigin
from dagster.core.storage.pipeline_run import PipelineRun
from dagster.grpc.client import DagsterGrpcClient
from dagster.grpc.server import ExecuteRunArgs
from dagster.serdes.ipc import (
    IPCErrorMessage,
    ipc_read_event_stream,
    open_ipc_subprocess,
    write_unary_input,
)
from dagster.utils import safe_tempfile_path


def cli_api_execute_run(output_file, instance, pipeline_origin, pipeline_run):
    check.str_param(output_file, 'output_file')
    check.inst_param(instance, 'instance', DagsterInstance)
    check.inst_param(pipeline_origin, 'pipeline_origin', PipelinePythonOrigin)
    check.inst_param(pipeline_run, 'pipeline_run', PipelineRun)

    from dagster.cli.api import ExecuteRunArgsLoadComplete

    with safe_tempfile_path() as input_file:
        write_unary_input(
            input_file,
            ExecuteRunArgs(
                pipeline_origin=pipeline_origin,
                pipeline_run_id=pipeline_run.run_id,
                instance_ref=instance.get_ref(),
            ),
        )

        parts = [
            pipeline_origin.executable_path,
            '-m',
            'dagster',
            'api',
            'execute_run',
            input_file,
            output_file,
        ]

        instance.report_engine_event(
            'About to start process for pipeline "{pipeline_name}" (run_id: {run_id}).'.format(
                pipeline_name=pipeline_run.pipeline_name, run_id=pipeline_run.run_id
            ),
            pipeline_run,
            engine_event_data=EngineEventData(marker_start='cli_api_subprocess_init'),
        )

        process = open_ipc_subprocess(parts)

        # we need to process this event in order to ensure that the called process loads the input
        event = next(ipc_read_event_stream(output_file))

        check.inst(event, ExecuteRunArgsLoadComplete)

        return process


def execute_run_grpc(api_client, instance_ref, pipeline_origin, pipeline_run):
    check.inst_param(api_client, 'api_client', DagsterGrpcClient)
    check.inst_param(instance_ref, 'instance_ref', InstanceRef)
    check.inst_param(pipeline_origin, 'pipeline_origin', PipelineGrpcServerOrigin)
    check.inst_param(pipeline_run, 'pipeline_run', PipelineRun)

    instance = DagsterInstance.from_ref(instance_ref)

    yield instance.report_engine_event(
        'About to start process for pipeline "{pipeline_name}" (run_id: {run_id}).'.format(
            pipeline_name=pipeline_run.pipeline_name, run_id=pipeline_run.run_id
        ),
        pipeline_run,
        engine_event_data=EngineEventData(marker_start='cli_api_subprocess_init'),
    )

    run_did_fail = False

    execute_run_args = ExecuteRunArgs(
        pipeline_origin=pipeline_origin,
        pipeline_run_id=pipeline_run.run_id,
        instance_ref=instance_ref,
    )
    for event in api_client.execute_run(execute_run_args=execute_run_args):
        if isinstance(event, IPCErrorMessage):
            yield instance.report_engine_event(
                event.message,
                pipeline_run=pipeline_run,
                engine_event_data=EngineEventData(
                    marker_end='cli_api_subprocess_init', error=event.serializable_error_info
                ),
            )
            if not run_did_fail:
                run_did_fail = True
                yield instance.report_run_failed(pipeline_run)
        else:
            yield event


def sync_execute_run_grpc(api_client, instance_ref, pipeline_origin, pipeline_run):
    return [
        event
        for event in execute_run_grpc(
            api_client=api_client,
            instance_ref=instance_ref,
            pipeline_origin=pipeline_origin,
            pipeline_run=pipeline_run,
        )
    ]
