import ctypes
import os
import re
import base64

# Define Windows CryptoAPI constants
X509_ASN_ENCODING = 0x00000001
CERT_STORE_ADD_REPLACE_EXISTING = 3

crypt32 = ctypes.windll.crypt32

# Open ROOT certificate store
crypt32.CertOpenSystemStoreW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
crypt32.CertOpenSystemStoreW.restype = ctypes.c_void_p

h_store = crypt32.CertOpenSystemStoreW(None, "ROOT")
if not h_store:
    print("Failed to open ROOT store")
    exit(1)

# CertAddEncodedCertificateToStore
crypt32.CertAddEncodedCertificateToStore.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.c_char_p,
    ctypes.c_ulong,
    ctypes.c_ulong,
    ctypes.c_void_p
]
crypt32.CertAddEncodedCertificateToStore.restype = ctypes.c_bool

# Load ca-certificates.crt from Unix path mapped in Wine (Z:\etc\ssl\certs\ca-certificates.crt)
unix_cert_path = r"Z:\etc\ssl\certs\ca-certificates.crt"

if not os.path.exists(unix_cert_path):
    print(f"Cert file not found: {unix_cert_path}")
    exit(1)

with open(unix_cert_path, "r") as f:
    certs_data = f.read()

# Parse PEM certificates
pem_certs = re.findall(r"-----BEGIN CERTIFICATE-----\n(.*?)\n-----END CERTIFICATE-----", certs_data, re.DOTALL)

print(f"Found {len(pem_certs)} PEM certificates to import.")

success_count = 0
for pem in pem_certs:
    der = base64.b64decode(pem.replace("\n", "").replace("\r", ""))
    res = crypt32.CertAddEncodedCertificateToStore(
        h_store,
        X509_ASN_ENCODING,
        der,
        len(der),
        CERT_STORE_ADD_REPLACE_EXISTING,
        None
    )
    if res:
        success_count += 1

# Explicitly close the store to persist and flush registry changes
crypt32.CertCloseStore.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
crypt32.CertCloseStore.restype = ctypes.c_bool
crypt32.CertCloseStore(h_store, 0)

print(f"Successfully imported {success_count} / {len(pem_certs)} certificates into Wine ROOT store.")
