from cryptography.x509 import ocsp, load_pem_x509_certificate
import base64
from cryptography.hazmat.primitives import serialization
import urllib

f = open("c.pem", "rb")
b = f.read()
f.close()

cert = load_pem_x509_certificate(b)

print(cert.serial_number)
print(cert.public_key())



issuer = load_pem_x509_certificate(pem_issuer)

builder = ocsp.OCSPRequestBuilder()
builder = builder.add_certificate(client_cert, issuer_cert, SHA1())
req = builder.build()
der_res = req.public_bytes(serialization.Encoding.DER)
req_path = base64.b64encode(der_res).decode("ascii")
ocsp_req_url = f"{ocsp_url}{req_path}"
print(ocsp_req_url)

req = urllib.request.Request(ocsp_req_url)

with urllib.request.urlopen(req) as res:
    body = res.read()
# validate the OCSP check
ocsp_resp = ocsp.load_der_ocsp_response(body)
print("ocsp response status: " + str(ocsp_resp.response_status))