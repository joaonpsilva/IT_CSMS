from aio_pika import ExchangeType, Message, connect
import uuid
import json
import asyncio
from typing import MutableMapping

from aio_pika.abc import (
    AbstractChannel, AbstractConnection, AbstractIncomingMessage, AbstractQueue,
)

import logging
logging.basicConfig(level=logging.INFO)

import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from rabbit_handler import Rabbit_Handler
            

class API_Rabbit_Handler(Rabbit_Handler):
    pass