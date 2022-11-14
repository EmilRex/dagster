import os

from assets_dbt_python.assets import forecasting, raw_data
from dagster_dbt import dbt_cli_resource, load_assets_from_dbt_project
from dagster_duckdb import build_duckdb_io_manager
from dagster_duckdb_pandas import DuckDBPandasTypeHandler

from dagster import (
    ScheduleDefinition,
    define_asset_job,
    definitions,
    file_relative_path,
    fs_io_manager,
    load_assets_from_package_module,
)

DBT_PROJECT_DIR = file_relative_path(__file__, "../dbt_project")
DBT_PROFILES_DIR = file_relative_path(__file__, "../dbt_project/config")

# all assets live in the default dbt_schema
dbt_assets = load_assets_from_dbt_project(
    DBT_PROJECT_DIR,
    DBT_PROFILES_DIR,
    # prefix the output assets based on the database they live in plus the name of the schema
    key_prefix=["duckdb", "dbt_schema"],
    # prefix the source assets based on just the database
    # (dagster populates the source schema information automatically)
    source_key_prefix=["duckdb"],
)

raw_data_assets = load_assets_from_package_module(
    raw_data,
    group_name="raw_data",
    # all of these assets live in the duckdb database, under the schema raw_data
    key_prefix=["duckdb", "raw_data"],
)

forecasting_assets = load_assets_from_package_module(
    forecasting,
    group_name="forecasting",
)

everything_job = define_asset_job("everything_everywhere_job", selection="*")
forecast_job = define_asset_job("refresh_forecast_model_job", selection="*order_forecast_model")

duckdb_io_manager = build_duckdb_io_manager(type_handlers=[DuckDBPandasTypeHandler()])

definitions(
    # this code was moved from repository.py which is not typechecked for some reason
    # not going to fix that issues right now
    assets=dbt_assets + raw_data_assets + forecasting_assets,  # type: ignore
    schedules=[
        ScheduleDefinition(job=everything_job, cron_schedule="@weekly"),
        ScheduleDefinition(job=forecast_job, cron_schedule="@daily"),
    ],
    resources={
        # this io_manager allows us to load dbt models as pandas dataframes
        "io_manager": duckdb_io_manager.configured(
            {"database": os.path.join(DBT_PROJECT_DIR, "example.duckdb")}
        ),
        # this io_manager is responsible for storing/loading our pickled machine learning model
        "model_io_manager": fs_io_manager,
        # this resource is used to execute dbt cli commands
        "dbt": dbt_cli_resource.configured(
            {"project_dir": DBT_PROJECT_DIR, "profiles_dir": DBT_PROFILES_DIR}
        ),
    },
)
