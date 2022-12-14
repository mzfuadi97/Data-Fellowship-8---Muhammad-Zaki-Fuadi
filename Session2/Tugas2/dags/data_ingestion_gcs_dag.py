import os
import logging

from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

from google.cloud import storage
from airflow.providers.google.cloud.operators.bigquery import BigQueryCreateExternalTableOperator
import pyarrow.csv as pv
import pyarrow.parquet as pq
import pandas as pd
import csv
import requests

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BUCKET = os.environ.get("GCP_GCS_BUCKET")
# PROJECT_ID = "fellowship-7"
# BUCKET = "fellowship-7"

# dataset_file = "yellow_tripdata_2021-01.csv"
# dataset_url = f"https://s3.amazonaws.com/nyc-tlc/trip+data/{dataset_file}"

dataset_file = "Nation_Population.csv"
dataset_url = f"https://datausa.io/api/data?drilldowns=Nation&measures=Population"

path_to_local_home = os.environ.get("AIRFLOW_HOME", "/opt/airflow/")
# path_to_local_home = "/opt/airflow/"
csv_filename = "Nation_Population.csv"
parquet_file = dataset_file.replace('.csv', '.parquet')
BIGQUERY_DATASET = os.environ.get("BIGQUERY_DATASET", 'session2')

def getData(ti): 
    data = requests.get('https://datausa.io/api/data?drilldowns=Nation&measures=Population')
    id_nation = []
    nation = []
    id_year = []
    year = []
    population = []
    slug_nation = []
    
    for i in data.json()['data']:
        id_nation.append(i['ID Nation'])
        nation.append(i['Nation'])
        id_year.append(int(i['ID Year']))
        year.append(int(i['Year']))
        population.append(int(i['Population']))
        slug_nation.append(i['Slug Nation'])

    result = {'ID Nation':id_nation, 'Nation':nation, "ID Year":id_year, "Year":year, "Population":population, "Slug Nation":slug_nation}
    ti.xcom_push(key = 'parsing_result', value = result)

def format_to_csv(ti, csv_filename):
    dict_result = ti.xcom_pull(task_ids='getData', key='parsing_result')
    df = pd.DataFrame(dict_result)
    df.to_csv('/opt/airflow/'+csv_filename, index=False)

def format_to_parquet(src_file):
    if not src_file.endswith('.csv'):
        logging.error("Can only accept source files in CSV format, for the moment")
        return
    table = pv.read_csv(src_file)
    pq.write_table(table, src_file.replace('.csv', '.parquet'))


# NOTE: takes 20 mins, at an upload speed of 800kbps. Faster if your internet has a better upload speed
def upload_to_gcs(bucket, object_name, local_file):
    """
    Ref: https://cloud.google.com/storage/docs/uploading-objects#storage-upload-object-python
    :param bucket: GCS bucket name
    :param object_name: target path & file-name
    :param local_file: source path & file-name
    :return:
    """
    # WORKAROUND to prevent timeout for files > 6 MB on 800 kbps upload speed.
    # (Ref: https://github.com/googleapis/python-storage/issues/74)
    storage.blob._MAX_MULTIPART_SIZE = 5 * 1024 * 1024  # 5 MB
    storage.blob._DEFAULT_CHUNKSIZE = 5 * 1024 * 1024  # 5 MB
    # End of Workaround

    client = storage.Client()
    bucket = client.bucket(bucket)

    blob = bucket.blob(object_name)
    blob.upload_from_filename(local_file)


default_args = {
    "owner": "airflow",
    "start_date": days_ago(1),
    "depends_on_past": False,
    "retries": 1,
}

# NOTE: DAG declaration - using a Context Manager (an implicit way)
with DAG(
    dag_id="data_ingestion_gcs_dag",
    schedule_interval="@daily",
    default_args=default_args,
    catchup=False,
    max_active_runs=1,
    tags=['IYKRA'],
) as dag:

    getData = PythonOperator(task_id='getData',
                                 python_callable=getData)

    format_to_csv_task = PythonOperator(
        task_id='format_to_csv_task',
        python_callable=format_to_csv,
        op_kwargs = {"csv_filename": csv_filename})

    format_to_parquet_task = PythonOperator(
        task_id="format_to_parquet_task",
        python_callable=format_to_parquet,
        op_kwargs={
            "src_file": f"{path_to_local_home}/{dataset_file}",
        },
    )

    local_to_gcs_task = PythonOperator(
        task_id="local_to_gcs_task",
        python_callable=upload_to_gcs,
        op_kwargs={
            "bucket": BUCKET,
            "object_name": f"raw/{parquet_file}",
            "local_file": f"{path_to_local_home}/{parquet_file}",
        },
    )

    bigquery_external_table_task = BigQueryCreateExternalTableOperator(
        task_id="bigquery_external_table_task",
        table_resource={
            "tableReference": {
                "projectId": PROJECT_ID,
                "datasetId": BIGQUERY_DATASET,
                "tableId": "external_table",
            },
            "externalDataConfiguration": {
                "sourceFormat": "PARQUET",
                "sourceUris": [f"gs://{BUCKET}/raw/{parquet_file}"],
            },
        },
    )

    getData >> format_to_csv_task >> format_to_parquet_task >> local_to_gcs_task >> bigquery_external_table_task
