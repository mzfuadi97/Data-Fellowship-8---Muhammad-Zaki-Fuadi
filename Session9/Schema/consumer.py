from confluent_kafka.avro import AvroConsumer
from google.cloud import bigquery
from google.oauth2 import service_account

# BIGQUERY API
creds = service_account.Credentials.from_service_account_file('/home/df8coba/session6/Avro/keys.json')
client_bq = bigquery.Client(credentials=creds)

client_bq.create_dataset('session9', exists_ok=True)
schema_bq = [
    bigquery.SchemaField('Date', 'STRING'),
    bigquery.SchemaField('Open', 'FLOAT'),
    bigquery.SchemaField('High', 'FLOAT'),
    bigquery.SchemaField('Low', 'FLOAT'),
    bigquery.SchemaField('Close', 'FLOAT'),
    bigquery.SchemaField('Volume', 'STRING'),
    bigquery.SchemaField('Market_Cap', 'STRING')
]

table_id = 'weighty-diorama-365805.session9.bitcoin_price'
table = bigquery.Table(table_id, schema=schema_bq)
table = client_bq.create_table(table)


def read_messages():
    consumer_config = {"bootstrap.servers": "localhost:9092",
                       "schema.registry.url": "http://localhost:8081",
                       "group.id": "bitcoin.price.avro.consumer.2",
                       "auto.offset.reset": "earliest"}

    consumer = AvroConsumer(consumer_config)
    consumer.subscribe(["bitcoin.price"])
    

    while(True):
        try:
            message = consumer.poll(5)
        except Exception as e:
            print(f"Exception while trying to poll messages - {e}")
        else:
            if message:
                print(f"Successfully poll a record from "
                      f"Kafka topic: {message.topic()}, partition: {message.partition()}, offset: {message.offset()}\n"
                      f"message key: {message.key()} || message value: {message.value()}")
                consumer.commit()
                
                bq_ingest = client_bq.insert_rows_json(table_id, [message.value()])

                if bq_ingest == []:
                    print('Rows Pushed to Bigquery')
                else:
                    print(f'Encountered erros while inserting: {bq_ingest}')
            else:
                print("No new messages at this point. Try again later.")

    consumer.close()


if __name__ == "__main__":
    read_messages()