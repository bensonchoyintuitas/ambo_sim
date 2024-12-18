<!-- run syntha api (optional) -->
Assumes synthea is in the same root folder as ambo_sim
synthea_api/source .venv/bin/activate 
synthea_api/python3 api.py

<!-- run kafka -->
ambo_sim/infrastructure/confluent/docker-compose up -d

<!-- run the simulator -->
ambo_sim/source .venv/bin/activate 
ambo_sim/python3 app.py --llm-model llama3.1:8b --fhir-export

<!-- run the producers -->
cd ambo_sim/tools/kafka_producer/

source .venv/bin/activate
python3 produce_json.py --input ../../fhir_export/session_20241214_212330/patient/ --output-topic patient --continuous 30

source .venv/bin/activate
python3 produce_json.py --input ../../fhir_export/session_20241214_212330/condition/ --output-topic condition --continuous 30

source .venv/bin/activate
python3 produce_json.py --input ../../fhir_export/session_20241214_212330/encounter_ed_presentation/ --output-topic encounter_ed_presentation --continuous 30

source .venv/bin/activate
python3 produce_json.py --input ../../fhir_export/session_20241214_212330/encounter_discharge/ --output-topic encounter_discharge --continuous 30

<!-- run the consumers -->
cd ambo_sim/tools/kafka_consumer_adls/

# patient
source .venv/bin/activate
python3 kafka_consumer_adls.py --topic patient \
                            --container dev \
                            --path bronze/landing/kafka__local/ \
                            --consumer-group DefaultConsumerGroup \
                            --bootstrap-server localhost:9092 \
                            --auto-offset earliest \
                            --reset-offset

# encounter_ed_presentation
source .venv/bin/activate
python3 kafka_consumer_adls.py --topic encounter_ed_presentation \
                            --container dev \
                            --path bronze/landing/kafka__local/ \
                            --consumer-group DefaultConsumerGroup \
                            --bootstrap-server localhost:9092 \
                            --auto-offset earliest \
                            --reset-offset

# encounter_discharge
source .venv/bin/activate
python3 kafka_consumer_adls.py --topic encounter_discharge \
                            --container dev \
                            --path bronze/landing/kafka__local/ \
                            --consumer-group DefaultConsumerGroup \
                            --bootstrap-server localhost:9092 \
                            --auto-offset earliest \
                            --reset-offset

# condition
source .venv/bin/activate
python3 kafka_consumer_adls.py --topic condition \
                            --container dev \
                            --path bronze/landing/kafka__local/ \
                            --consumer-group DefaultConsumerGroup \
                            --bootstrap-server localhost:9092 \
                            --auto-offset earliest \
                            --reset-offset