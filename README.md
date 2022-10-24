
## Python libraries
pip install uvicorn  
pip install fastapi  
pip install aio-pika  
pip install ocpp  
pip install websockets  
pip install sqlalchemy  
pip install pymysql  
pip install passlib
pip install aioconsole (apenas para debug)

## Rabbit MQ Server
sudo docker run -it --rm --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management


## MySql Server

### DOCKER
-----Criar container  
sudo docker run -p 3306:3306 --name=mysql_CSMS -d mysql/mysql-server

-----Password gerada  
sudo docker logs mysql_CSMS 2>&1 | grep GENERATED

-----Acessar linha de comandos mysql  
sudo docker exec -it mysql_CSMS mysql -uroot -p

-----Substituir password e dar permissoes a outras conexoes  
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'password123';
update mysql.user set host = '%' where user='root';
flush privileges;

### Intall locally

https://dev.to/gsudarshan/how-to-install-mysql-and-workbench-on-ubuntu-20-04-localhost-5828

if workbench installed with snap (allow manager to connect):  
sudo snap connect mysql-workbench-community:password-manager-service :password-manager-service
