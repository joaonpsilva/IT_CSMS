import base64
import ssl
import requests
from urllib.parse import urljoin
import datetime
import os
import wget
import traceback

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.x509 import ocsp
from cryptography.x509.ocsp import OCSPResponseStatus
from cryptography.x509.oid import ExtensionOID, AuthorityInformationAccessOID
from cryptography.x509 import NameOID
from hashlib import sha256
import ecdsa
from ecdsa.util import sigdecode_der
from cryptography.hazmat.primitives.asymmetric import padding
import os

cert_dict = {}
path_to_rootCA = os.fsencode("certs/root/")
    
for file in os.listdir(path_to_rootCA):
    filename = os.fsdecode(file)
    if filename.endswith(".pem"):
        data = open(os.path.join(path_to_rootCA, filename), "rb")
        data = data.read()
        cert = x509.load_pem_x509_certificate(data, default_backend())
        cert_dict[cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value] = cert
     

def get_issuer_name(cert):
    autenticador = cert.issuer.get_attributes_for_oid(
        NameOID.COMMON_NAME)  # lista com os atributos da entidade certificadora
    autenticador = autenticador[0].value

    return autenticador

def get_issuer_url(cert):
    aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
    issuers = [ia for ia in aia if ia.access_method == AuthorityInformationAccessOID.CA_ISSUERS]
    if not issuers:
        raise Exception(f'no issuers entry in AIA')
    return issuers[0].access_location.value

def get_issuer_cert(ca_issuer):
    issuer_response = requests.get(ca_issuer)
    if issuer_response.ok:
        issuerDER = issuer_response.content
        issuerPEM = ssl.DER_cert_to_PEM_cert(issuerDER)
        return x509.load_pem_x509_certificate(issuerPEM.encode('ascii'), default_backend())
    raise Exception(f'fetching issuer cert  failed with response status: {issuer_response.status_code}')

def get_ocsp_server(cert):
    aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
    ocsps = [ia for ia in aia if ia.access_method == AuthorityInformationAccessOID.OCSP]
    if not ocsps:
        raise Exception(f'no ocsp server entry in AIA')
    return ocsps[0].access_location.value


def verify_with_issuer(cert, issuer_cert):  # cert = certificado a validar, issuer= entidade acima na cadeia
    try:
        issuer_public_key = issuer_cert.public_key()

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
        #print(traceback.format_exc())
        return False


def check_crl(cert):   
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
        print("CRL não encontrado")
        return False
    
    return True


def validate_cert(self,cert, crl=False):
    cert = x509.load_pem_x509_certificate(cert, default_backend())
    flag = False 
    
    while True:
        #Date validation
        if not cert.not_valid_before < datetime.datetime.now() < cert.not_valid_after:
            print("Certificado expirado")
            return False
        
        # vê o issuer
        issuer = get_issuer_name(cert)  
        # Vê se consegue estabelecer uma cadeia ( se o issuer está np dicionario com os issuers conhecidos)
        if issuer is None:
            return False
        elif issuer in cert_dict:
            issuer_cert = cert_dict[issuer]
            flag = True
        else:
            issuer = get_issuer_url(cert)
            issuer_cert = get_issuer_cert(issuer)   
            
        # Valida a chave publica do cert, com as informações do issuer
        if not verify_with_issuer(cert, issuer_cert):
            #Certificado não foi validado pelo issuer
            return False

        # Se o issuer for o mesmo que o cert, ele será autovalidado
        if cert != issuer_cert:
            if crl:
                if not check_crl(cert):
                    return False
        
        if flag:
            return True
        
        cert=issuer_cert


def ocsp_request(hash_algorithm, issuer_name_hash, issuer_key_hash, serial_number, responder_url):

    issuer_name_hash = bytes.fromhex(issuer_name_hash)
    issuer_key_hash = bytes.fromhex(issuer_key_hash)
    serial_number = int(serial_number)
    hash_algorithm = getattr(hashes, hash_algorithm)()

    builder = ocsp.OCSPRequestBuilder()
    builder= builder.add_certificate_by_hash(issuer_name_hash, issuer_key_hash, serial_number, hash_algorithm)
    req = builder.build()

    der_res = req.public_bytes(serialization.Encoding.DER)
    req_path = base64.b64encode(der_res).decode("ascii")

    ocsp_resp = requests.get(urljoin(responder_url + '/', req_path))

    if ocsp_resp.ok:
        ocsp_decoded = ocsp.load_der_ocsp_response(bytes.fromhex(ocsp_resp.content.decode("utf-8")[1:-1]))
        if ocsp_decoded.response_status == OCSPResponseStatus.SUCCESSFUL:
            print(ocsp_decoded)
            return ocsp_decoded.certificate_status == ocsp.OCSPCertStatus.GOOD
        else:
            print(f'decoding ocsp response failed: {ocsp_decoded.response_status}')
            return False
    print(f'fetching ocsp cert status failed with response status: {ocsp_resp.status_code}')
    return False