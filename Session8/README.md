# Objectives
Create a step-by-step demo on how to stream tables from Postgres to Kafka/ksqlDB and back to Postgres.

## Data
- The data used here was originally taken from the [Graduate Admissions](https://www.kaggle.com/mohansacharya/graduate-admissions) open dataset available on Kaggle.
- The admit csv files are records of students and test scores with their chances of college admission.
- The research csv files contain a flag per student for whether or not they have research experience.

# Requirements
The following technologies are used through Docker containers:
* Kafka, the streaming platform
* Zookeeper, Kafka's best friend
* KSQL server, which we will use to create real-time updating tables
* Kafka's schema registry, needed to use the Avro data format
* Kafka Connect, pulled from [debezium](https://debezium.io/), which will source and sink data back and forth through Kafka
* Postgres, pulled from debezium, tailored for use with Connect

# How to Run

1. Build the image
```
docker build -t debezium-connect -f debezium.Dockerfile .
```
2. Activate the containers
```
docker-compose up -d
```
3. Login to PostgreSQL
```
docker run -it --rm --network={name_folder}_default \
         -v $PWD:/home/data/ \
         postgres:11.0 psql -h postgres -U postgres
```
Password = postgres
Note: Dont forget to export your project directory path to PWD variable!
4. Create and connect to the database
```
CREATE DATABASE bankmarketing;
```
```
\connect bankmarketing;
```
5. Create table and insert data to table (admission)
```
CREATE TABLE marketingcall (id INTEGER, age INTEGER, job VARCHAR, martial VARCHAR, education VARCHAR, contact VARCHAR, housing VARCHAR, month VARCHAR, duration INTEGER, campaign VARCHAR, y VARCHAR, CONSTRAINT id_pk PRIMARY KEY (id));
```
```
\copy admission FROM '/home/data/bank-addtional-full.csv' DELIMITER ';' CSV HEADER
```

7. Connect Postgres database to Kafka
```
curl -X POST -H "Accept:application/json" -H "Content-Type: application/json" \
      --data @postgres-source.json http://localhost:8083/connectors
```
8. See the list of existing connectors:
```
curl -H "Accept:application/json" localhost:8083/connectors/
```
9. Listing the available topics:
```
docker exec -it <cp-zookeeper-container-id> /bin/bash
```
```
/usr/bin/kafka-topics --list --zookeeper zookeeper:2181
```
10. Login to ksqlDB
```
docker run --network name_folder_default \
           --interactive --tty --rm \
           confluentinc/cp-ksql-cli:latest \
           http://ksql-server:8088
```
11. Configure some settings
```
set 'commit.interval.ms'='2000';
```
```
set 'cache.max.bytes.buffering'='10000000';
```
```
set 'auto.offset.reset'='earliest';
```
12. The Postgres table topics will be visible in ksqlDB, and we will create ksqlDB streams to auto update ksqlDB tables mirroring the Postgres tables:
```
SHOW TOPICS;
```
```
CREATE STREAM stream_table (id INTEGER, age INTEGER, job VARCHAR, martial VARCHAR, education VARCHAR, contact VARCHAR, housing VARCHAR, month VARCHAR, duration INTEGER, campaign VARCHAR, y VARCHAR) WITH (KAFKA_TOPIC='dbserver1.public.marketingcall', VALUE_FORMAT='AVRO');
```
```
SHOW STREAMS;
```



13. Create downstream tables. We will create a new ksqlDB streaming table to join students' chance of admission with research experience.
```
CREATE TABLE final_table  AS \
      SELECT month, SUM(duration) as total_duration, COUNT(*) as qty_of_month \
      FROM stream_table GROUP BY 1; 
```

14. Add a connector to sink a KSQL table back to Postgres

The postgres-sink.json configuration file will create a RESEARCH_AVE_BOOST
table and send the data back to Postgres.

```
curl -X POST -H "Accept:application/json" -H "Content-Type: application/json" \
      --data @postgres-sink.json http://localhost:8083/connectors
```

15. Update the source Postgres tables and watch the Postgres sink table update

The final_table table should now be available in Postgres to query:
