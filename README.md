# Charging Station Management System

Central system to manage EV charging stations using OCPP 2.0.1 protocol

## Run With Docker Compose

- cd src
- docker-compose up

## (ALTERNATIVELY) Run individually

Install requirements:
 - pip install -r requirements.txt

### MySql Server Docker container

Criar container  
-  sudo docker run -p 3306:3306 --name=mysql_CSMS -d mysql/mysql-server

Password gerada
- sudo docker logs mysql_CSMS 2>&1 | grep GENERATED

Acessar linha de comandos mysql  
- sudo docker exec -it mysql_CSMS mysql -uroot -p

Substituir password para 'password123' e dar permissoes a outras conexoes  
- ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'password123';
- update mysql.user set host = '%' where user='root';
- flush privileges;

Criar base de dados
- CREATE DATABASE csms_db;
- cntr+D

Start Container
- sudo docker start mysql_CSMS

Alternatively it should be possible to install mysql locally:  
<https://dev.to/gsudarshan/how-to-install-mysql-and-workbench-on-ubuntu-20-04-localhost-5828>


### Rabbit MQ Server Docker
- sudo docker run --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

### CSMS
- cd src
- python3 -m CSM

**OR**

- ./run_CSMS.sh

**OR**

- cd src
- python3 -m CSMS.api.api
- python3 -m CSMS.ocpp_server.ocpp_server
- python3 -m CSMS.db.db


# Client

Simple client that forwards messages
- python3 -m charge_station.client.simple_ocpp_client

Mock client to test messages
- python3 charge_station/mocks/mock_charge_station.py CP_1

Simulation
- python3 charge_station/mocks/simulation.py -p [update_period (will reflect in csms db)] -f [factor (speed up)]


