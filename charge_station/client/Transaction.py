class Transaction:
    def __init__(self, transaction_id):
        self.transaction_id=transaction_id

        self._start_idToken = None
        self._group_idToken = None
        self._evseId=None
        self._connectorId=None
        self._authorized = False
    
    @property
    def authorized(self):
        return self._authorized

    @authorized.setter
    def authorized(self, value):
        self._authorized = value

    
    @property
    def evseId(self):
        return self._evseId

    @evseId.setter
    def evseId(self, value):
        self._evseId = value
    

    @property
    def connectorId(self):
        return self._connectorId

    @connectorId.setter
    def connectorId(self, value):
        self._connectorId = value


    @property
    def start_idToken(self):
        return self._start_idToken

    @start_idToken.setter
    def start_idToken(self, value):
        if self._start_idToken is None:
            self._start_idToken = value
    

    @property
    def group_idToken(self):
        return self._group_idToken

    @group_idToken.setter
    def group_idToken(self, value):
        if self._group_idToken is None:
            self._group_idToken = value
    
    
    def check_valid_stop_with_Idtoken(self, idtoken):
        if self.start_idtoken is None:
            return True
        if idtoken["id_token"] == self.start_idtoken["id_token"]:
            return True
        
        return False
        

    def check_valid_stop_with_GroupIdtoken(self, group_id):
        if group_id["id_token"] == self.group_id["id_token"]:
            return True 
                
        return False

