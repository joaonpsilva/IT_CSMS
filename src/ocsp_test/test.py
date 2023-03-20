from cryptography.x509 import ocsp

ocsp_req = ocsp.load_der_ocsp_request("c.pem")

print(ocsp_req.serial_number)