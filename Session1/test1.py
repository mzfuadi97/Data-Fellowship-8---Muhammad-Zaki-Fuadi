from google.cloud import storage
import wget
import os

os.environ["GCLOUD_PROJECT"]='weighty-diorama-365805'
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]= 'key.json'

project_id = 'weighty-diorama-365805'
bucket_name = 'data-fellowship08-nyoba'
destination_blob_name = 'homes.csv'
storage_client = storage.Client()


source_file_name = 'https://people.sc.fsu.edu/~jburkardt/data/csv/homes.csv'

def upload_blob(bucket_name, source_file_name, destination_blob_name):   
    wget.download(source_file_name, 'homes.csv')

    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename('homes.csv')

upload_blob(bucket_name, source_file_name, destination_blob_name)