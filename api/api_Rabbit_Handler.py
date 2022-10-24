
import logging
logging.basicConfig(level=logging.INFO)

import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from rabbit_handler import Rabbit_Handler
            

class API_Rabbit_Handler(Rabbit_Handler):
    pass