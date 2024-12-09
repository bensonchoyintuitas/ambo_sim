# References
https://hub.docker.com/r/confluentinc/cp-kafka/
https://docs.confluent.io/platform/current/platform-quickstart.html#ce-docker-quickstart
https://github.com/confluentinc/cp-all-in-one/blob/7.5.2-post/cp-all-in-one-kraft/docker-compose.yml
https://ksqldb.io/quickstart-platform.html#quickstart-content

# design
* because datahub uses kafka, all ports have had +100 and all containers and hosts are appended with _01


# instructions
1. run
docker-compose up -d
docker-compose ps
1. Navigate to Control Center at http://localhost:9021. / http://desktop3080:9021/
2. stop
docker-compose stop

<!-- To get into a container and consumer test -->
docker exec -it broker_01 /bin/bash
<!-- default -->
kafka-console-producer --broker-list localhost:9092 --topic synthea_raw
<!-- rn -->
kafka-console-producer --broker-list localhost:9098 --topic synthea_raw

<!-- default -->
kafka-console-consumer --bootstrap-server localhost:9092 --topic synthea_raw --from-beginning
<!-- rn -->
kafka-console-consumer --bootstrap-server localhost:9098 --topic synthea_raw --from-beginning

# clean up
docker system prune -a --volumes --filter "label=io.confluent.docker"