
import os
import requests
import wget
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import datetime
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import NameOID
from cryptography.x509.oid import ExtensionOID

cert_dict = {}

def get_issuer(cert):
        autenticador = cert.issuer.get_attributes_for_oid(
            NameOID.COMMON_NAME)  # lista com os atributos da entidade certificadora
        autenticador = autenticador[0].value

        return autenticador

def validate_time(cert):
        not_valid_before = cert.not_valid_before
        not_valid_after = cert.not_valid_after
        now = datetime.datetime.now()
        if not (not_valid_before < now < not_valid_after):
            return False
        return True


def validate_issuer(cert, issuer):  # cert = certificado a validar, issuer= entidade acima na cadeia
        from cryptography.hazmat.primitives import serialization, hashes
        from hashlib import sha256
        import ecdsa
        from ecdsa.util import sigdecode_der

        try:
            issuer_public_key = issuer.public_key()

            # Verify the signature using the public key

            try:
                #hubject certificaye
                ecdsa_key = issuer_public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)
                vk = ecdsa.VerifyingKey.from_pem(ecdsa_key)
                vk.verify(cert.signature, cert.tbs_certificate_bytes, hashfunc=sha256, sigdecode=sigdecode_der)
            except:

                #Regular Certificate
                issuer_public_key.verify(cert.signature,cert.tbs_certificate_bytes,padding.PKCS1v15(),cert.signature_hash_algorithm)

            return True
        except:
            import traceback
            print(traceback.format_exc())
            return False
            

def validate_cert(cert, flag=False):
    # verifica a data de validade
    if not validate_time(cert):  # Verifica a data
        print("Certificado expirado")
        return False

    # vê o issuer
    issuer = get_issuer(cert)  
    # Vê se consegue estabelecer uma cadeia ( se o issuer está np dicionario com os issuers conhecidos)
    if issuer not in cert_dict or issuer is None:
        print("Não foi possivel estabelecer uma cadeia de certificados")
        return False

    # Valida a chave publica do cert, com as informações do issuer
    issuer_cert = cert_dict[issuer]
    if not validate_issuer(cert, issuer_cert):
        print("Certificado não foi validado pelo issuer")
        return False

    # Se o issuer for o mesmo que o cert, ele será autovalidado
    if cert == issuer_cert:
        return True

    return True



data = open("certs/ca.pem", "rb")
data = data.read()
cert = x509.load_pem_x509_certificate(data, default_backend())
cert_dict[cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value] = cert
print(validate_cert(cert))


data = open("certs/intermidiate.crt", "rb")
data = data.read()
cert = x509.load_pem_x509_certificate(data, default_backend())
cert_dict[cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value] = cert
print(validate_cert(cert))


data = open("certs/leaf.crt", "rb")
data = data.read()
cert = x509.load_pem_x509_certificate(data, default_backend())
cert_dict[cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value] = cert
print(validate_cert(cert))