class ValidationError(Exception):
    def __init__(self, message):
        self.status = "VAL_ERROR"          
        super().__init__(message)


class OtherError(Exception):
    def __init__(self, message):    
        self.status = "OTHER_ERROR"          
        super().__init__(message)