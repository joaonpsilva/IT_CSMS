import uvicorn
from fastapi import FastAPI
import base64

import datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509 import load_pem_x509_certificate, ocsp
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import Encoding
app = FastAPI()

data = open("certs/leaf/leaf.crt", "rb")
data = data.read()
cert = load_pem_x509_certificate(data, default_backend())

data = open("certs/intermidiate/intermidiate.crt", "rb")
data = data.read()
issuer_cert = load_pem_x509_certificate(data, default_backend())

data = open("certs/intermidiate/intermidiate.key", "rb")
data = data.read()
responder_key = serialization.load_pem_private_key(data, None)


@app.get("/ocsp_intermidiate/{cert_data:path}")
def ocsp_endpoint(cert_data):

    #cert_data = bytes(cert_data, encoding="ascii")
    #cert_data = base64.b64decode(cert_data)
    #ocsp_req = ocsp.load_der_ocsp_request(cert_data)

    builder = ocsp.OCSPResponseBuilder()
    builder = builder.add_response(
        cert=cert,
        issuer=issuer_cert, algorithm=hashes.SHA256(),
        cert_status=ocsp.OCSPCertStatus.GOOD,
        this_update=datetime.datetime.now(),
        next_update=datetime.datetime.now(),
        revocation_time=None, revocation_reason=None
    ).responder_id(
        ocsp.OCSPResponderEncoding.HASH, issuer_cert
    )
    response = builder.sign(responder_key, hashes.SHA256())
    
    return response.public_bytes(Encoding.DER).hex()

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8001,loop= 'asyncio')