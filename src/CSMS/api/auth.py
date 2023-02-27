import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from datetime import datetime, timedelta
import os
import binascii

class AuthHandler():
    
    security = HTTPBearer()
    secret = binascii.hexlify(os.urandom(24))

    def encode_token(self, user_info):
        
        exp_info = {
            "exp" : datetime.utcnow() + timedelta(minutes=10),
            "iat" : datetime.utcnow()
        }
        payload = {**user_info, **exp_info}

        return jwt.encode(payload,self.secret,algorithm="HS256")

    def decode_token(self, token):
        try:
            payload = jwt.decode(token, self.secret, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, detail="signature has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(401, detail="Invalid token")
    

    def check_permission_level_1(self, auth: HTTPAuthorizationCredentials = Security(security)):
        user = self.decode_token(auth.credentials)

        if user["permission_level"] < 1:
            raise HTTPException(401, "Not enough permission level")
        
        return user


    def check_permission_level_2(self, auth: HTTPAuthorizationCredentials = Security(security)):
        user = self.decode_token(auth.credentials)

        if user["permission_level"] < 2:
            raise HTTPException(401, "Not enough permission level")
        
        return user