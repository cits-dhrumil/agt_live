# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
import base64


def load_private_key(private_key_path):
    """Load private key (1024 bits) from file"""
    with open(private_key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend()
        )
    return private_key

def generate_signature(message, private_key):
    """Generate a signature based on SHA-1 and PKCS1 v1.5 padding"""
    signature = private_key.sign(
        message.encode('utf-8'),  # Encode message using UTF-8
        padding.PKCS1v15(),       # Use PKCS1 v1.5 padding
        hashes.SHA1()             # Use SHA-1 hash algorithm
    )
    return signature

def encode_base64(data):
    """Base64 encode the data"""
    return base64.b64encode(data).decode('utf-8')

def hash(self, manual, datadocumento, datasistema, number, numHash, antigoHash, totalbruto):
    '''This method is use for generating hash value'''

    data = str(datadocumento) + ';' + datasistema.replace(" ",
                                                          "T") + ';' + number + ';' + str(
        totalbruto) + ';'
    if numHash > 0:
        data += antigoHash

    private_key_path = "/home/odoo/src/user/caretit_privatekey.pem"
    private_key = load_private_key(private_key_path)
    previous_hash = generate_signature(data, private_key)
    # Base64 encode the signature
    previous_hash = encode_base64(previous_hash)
    values = {'hash': previous_hash, 'hash_date': datasistema}
    return values
