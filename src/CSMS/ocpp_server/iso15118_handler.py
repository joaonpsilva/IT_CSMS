import base64
import ssl
import requests
from urllib.parse import urljoin
import datetime
import os
import wget

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


class ISO15118_Handler:

    cert_dict={}

    def __init__(self, cert):
        self.cert = x509.load_pem_x509_certificate(cert, default_backend())
        self.issuer = None
        self.issuer_cert = None


    def check_issuer(self):
        autenticador = self.cert.issuer.get_attributes_for_oid(
            NameOID.COMMON_NAME)  # lista com os atributos da entidade certificadora
        self.issuer = autenticador[0].value

        if self.issuer in ISO15118_Handler.cert_dict:
            self.issuer_cert = ISO15118_Handler.cert_dict[self.issuer]


    def validate_time(self):
            not_valid_before = self.cert.not_valid_before
            not_valid_after = self.cert.not_valid_after
            now = datetime.datetime.now()
            if not (not_valid_before < now < not_valid_after):
                return False
            return True


    def validate_issuer(self):  # cert = certificado a validar, issuer= entidade acima na cadeia
            
            try:
                issuer_public_key = self.issuer_cert.public_key()

                # Verify the signature using the public key
                try:
                    #hubject certificaye
                    ecdsa_key = issuer_public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)
                    vk = ecdsa.VerifyingKey.from_pem(ecdsa_key)
                    vk.verify(self.cert.signature, self.cert.tbs_certificate_bytes, hashfunc=sha256, sigdecode=sigdecode_der)
                except:

                    #Regular Certificate
                    issuer_public_key.verify(self.cert.signature,self.cert.tbs_certificate_bytes,padding.PKCS1v15(),self.cert.signature_hash_algorithm)

                return True
            except:
                import traceback
                print(traceback.format_exc())
                return False
    

    def validate_cert(self, flag=False):
        # verifica a data de validade
        if not self.validate_time():  # Verifica a data
            print("Certificado expirado")
            return False

        # vê o issuer
        self.check_issuer()  

        # Vê se consegue estabelecer uma cadeia ( se o issuer está np dicionario com os issuers conhecidos)
        if self.issuer_cert is None:
            print("Não foi possivel estabelecer uma cadeia de certificados")
            return False

        # Valida a chave publica do cert, com as informações do issuer
        if not self.validate_issuer():
            print("Certificado não foi validado pelo issuer")
            return False

        # Se o issuer for o mesmo que o cert, ele será autovalidado
        if self.cert == self.issuer_cert:
            return True

        # Caso não seja autovalidado, será verificada se pertence à lista de CRL do issuer
        # DOWNLOAD DA CRL DA INTERNET
        try:
            crl_url = (self.cert.extensions.get_extension_for_oid(ExtensionOID.CRL_DISTRIBUTION_POINTS).value[0].full_name[0].value)
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
            if self.cert in crl:
                print("Certificado Revogado")
                os.remove(CRL)
                return False
            os.remove(CRL)
        except:
            if not flag:
                print("CRL não encontrado")
                return False
            
            
    def get_issuer_url(self):
        aia = self.cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
        issuers = [ia for ia in aia if ia.access_method == AuthorityInformationAccessOID.OCSP]
        if not issuers:
            raise Exception(f'no issuers entry in AIA')
        return issuers[0].access_location.value
    

    def ocsp_request(self, hash_algorithm, issuer_name_hash, issuer_key_hash, serial_number, responder_url):
        builder = ocsp.OCSPRequestBuilder()
        builder.add_certificate_by_hash(bytes(issuer_name_hash, encoding="utf-8"), bytes(issuer_key_hash, encoding="utf-8"), int(serial_number), getattr(hashes, hash_algorithm)())
        req = builder.build()

        der_res = req.public_bytes(serialization.Encoding.DER)
        req_path = base64.b64encode(der_res).decode("ascii")

        ocsp_resp = requests.get(urljoin(responder_url + '/', req_path))

        if ocsp_resp.ok:
            ocsp_decoded = ocsp.load_der_ocsp_response(ocsp_resp.content)
            if ocsp_decoded.response_status == OCSPResponseStatus.SUCCESSFUL:
                return ocsp_decoded.certificate_status
            else:
                raise Exception(f'decoding ocsp response failed: {ocsp_decoded.response_status}')
        raise Exception(f'fetching ocsp cert status failed with response status: {ocsp_resp.status_code}')
