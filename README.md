
### Python libraries
pip install uvicorn
pip install fastapi
pip install aio-pika
pip install ocpp
pip install websockets
pip install mysql-connector-python
pip install aioconsole (apenas para debug)

### Rabbit MQ Server
sudo docker run -it --rm --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management


### MySql Server
sudo docker run -p 3306:3306 --name=mysql_CSMS -d mysql/mysql-server

Acessar linha de comandos mysql
sudo docker exec -it mysql_CSMS mysql -uroot -p