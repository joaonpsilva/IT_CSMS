
import os
import requests
import wget
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import datetime
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import NameOID
from cryptography.x509.oid import ExtensionOID


# try:
#     # Verify the EV's certificate chain
#     ev_cert_chain = [ev_cert, ca_certificate]
#     x509.verify_certificate_chain(ev_cert_chain, hashes.SHA256())

#     # Verify the EV's signature
#     if isinstance(ev_public_key, RSAPublicKey):
#         ev_public_key.verify(
#             ev_signature,
#             ev_certificate,
#             padding.PKCS1v15(),
#             hashes.SHA256()
#         )
#     elif isinstance(ev_public_key, EllipticCurvePublicKey):
#         ev_public_key.verify(
#             ev_signature,
#             ev_certificate.tbs_certificate_bytes,
#             ec.ECDSA(hashes.SHA256())
#         )


data = open("root.pem", "rb")
data = data.read()
cert = x509.load_pem_x509_certificate(data, default_backend())

cert_dict = {cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value : cert}

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
            #issuer_public_key.verify(cert.signature,cert.tbs_certificate_bytes,cert.signature_hash_algorithm)

            # Verify the signature using the public key
            ecdsa_key = issuer_public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)
            vk = ecdsa.VerifyingKey.from_pem(ecdsa_key)
            vk.verify(cert.signature, cert.tbs_certificate_bytes, hashfunc=sha256, sigdecode=sigdecode_der)

            return True
        except:
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

    # Caso não seja autovalidado, será verificada se pertence à lista de CRL do issuer
    # DOWNLOAD DA CRL DA INTERNET
    try:
        crl_url = (cert.extensions.get_extension_for_oid(ExtensionOID.CRL_DISTRIBUTION_POINTS).value[0].full_name[0].value)
        CRL = wget.download(crl_url,bar="")
        # Leitura da CRL descarregada
        path = os.path.abspath(CRL)
        data = open(path, "rb")
        data = data.read()
        try:
            crl = x509.load_pem_x509_crl(data, default_backend())   
        except:
            crl = x509.load_der_x509_crl(data, default_backend())
        # Verificação se o certificado está na CRL
        if cert in crl:
            print("Certificado Revogado")
            os.remove(CRL)
            return False
        os.remove(CRL)
    except:
        if not flag:
            print("CRL não encontrado")
            return False

print(validate_cert(cert))