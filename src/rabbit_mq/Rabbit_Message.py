import uuid

class Rabbit_Message:
    def routing_key(self):
        raise NotImplementedError
    def prepare_Response(self):
        raise NotImplementedError
    def to_dict(self):
        raise NotImplementedError
    def create_request_id(self):
        raise NotImplementedError


class Topic_Message(Rabbit_Message):
    def __init__(self, destination = None, origin = None, method = None,type = None,content = None,cp_id = None,status=None):
        self.destination = destination
        self.origin = origin
        self.method = method
        self.type = type
        self.content = content
        self.cp_id = cp_id
        self.status=status

    def routing_key(self):
        s=self.type
        if self.destination!=None:
            s += "." + self.destination
        if self.cp_id!=None:
            s += "." + self.cp_id
        return s

    def prepare_Response(self, status, **kwargs):
        temp_destination = self.destination
        self.destination = self.origin
        self.origin = temp_destination
        self.type = "response"
        self.content = None
        self.status = status
        return self

    def create_request_id(self):
        return str(uuid.uuid4())

class Fanout_Message(Rabbit_Message):
    def __init__(self, intent = None, type = None,content = None):
        self.intent = intent
        self.type = type
        self.content = content
    
    @property
    def destination(self):
        return "Decision_point"
    
    def routing_key(self):
        return ''
    
    def prepare_Response(self, **kwargs):
        self.type = "response"
        self.content = None
        return self

    def create_request_id(self):
        return self.intent