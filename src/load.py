"""
load.py
-------
Load step: writes the cleaned tables into a warehouse.

Default target: DuckDB, written to data/processed/warehouse.duckdb. DuckDB is
a real embedded SQL warehouse (columnar, full SQL) -- using it means anyone
who clones this repo can run the whole pipeline and query the result with
zero cloud setup or credentials.

Optional target: BigQuery. If GOOGLE_APPLICATION_CREDENTIALS and
BIGQUERY_PROJECT are set in the environment, load_to_bigquery() below loads
the same cleaned tables into a real cloud data warehouse -- the target this
project was designed for. The transform/validate/anomaly logic upstream of
this step is identical either way; only the last step changes.
"""

import os
from pathlib import Path
import duckdb
import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
DUCKDB_PATH = PROCESSED_DIR / "warehouse.duckdb"


def load_to_duckdb(tables: dict) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH))
    for name, df in tables.items():
        con.register("tmp_df", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp_df")
        con.unregister("tmp_df")
        # Also drop a CSV copy so the cleaned data is inspectable without a
        # SQL client -- useful for a quick diff against the raw source.
        df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False)
    con.close()
    print(f"Loaded {len(tables)} tables into {DUCKDB_PATH}")


def load_to_bigquery(tables: dict) -> None:
    """Optional: loads the same cleaned tables into BigQuery instead of/in
    addition to DuckDB. Requires:
        pip install google-cloud-bigquery
        export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
        export BIGQUERY_PROJECT=your-gcp-project-id
        export BIGQUERY_DATASET=audax_portfolio_pipeline   (optional, defaults below)
    """
    project = os.environ.get("BIGQUERY_PROJECT")
    if not project:
        raise RuntimeError(
            "BIGQUERY_PROJECT is not set. Set it (and "
            "GOOGLE_APPLICATION_CREDENTIALS) to load into BigQuery, or just "
            "use load_to_duckdb() -- no credentials needed."
        )
    from google.cloud import bigquery  # imported lazily: not a hard dependency

    dataset = os.environ.get("BIGQUERY_DATASET", "audax_portfolio_pipeline")
    client = bigquery.Client(project=project)

    dataset_ref = bigquery.DatasetReference(project, dataset)
    try:
        client.get_dataset(dataset_ref)
    except Exception:
        client.create_dataset(bigquery.Dataset(dataset_ref))

    for name, df in tables.items():
        table_ref = dataset_ref.table(name)
        job = client.load_table_from_dataframe(
            df, table_ref, job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
        )
        job.result()
        print(f"Loaded {len(df)} rows into BigQuery table {project}.{dataset}.{name}")


def query(sql: str) -> pd.DataFrame:
    """Convenience: run a SQL query against the DuckDB warehouse."""
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    result = con.execute(sql).fetchdf()
    con.close()
    return result
