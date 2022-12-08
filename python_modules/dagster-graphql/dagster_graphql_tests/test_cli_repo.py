from dagster import Int, ScheduleDefinition, op, repository
from dagster._legacy import InputDefinition, OutputDefinition, pipeline


@op(input_defs=[InputDefinition("num", Int)], output_defs=[OutputDefinition(Int)])
def add_one(num):
    return num + 1


@op(input_defs=[InputDefinition("num", Int)], output_defs=[OutputDefinition(Int)])
def mult_two(num):
    return num * 2


@pipeline
def math():
    mult_two(add_one())


@op(config_schema={"gimme": str})
def needs_config(context):
    return context.solid_config["gimme"]


@op
def no_config():
    return "ok"


@pipeline
def subset_test():
    no_config()
    needs_config()


def define_schedules():
    math_hourly_schedule = ScheduleDefinition(
        name="math_hourly_schedule",
        cron_schedule="0 0 * * *",
        job_name="math",
        run_config={"solids": {"add_one": {"inputs": {"num": {"value": 123}}}}},
    )

    return [math_hourly_schedule]


@repository
def test():
    return [math, subset_test] + define_schedules()
