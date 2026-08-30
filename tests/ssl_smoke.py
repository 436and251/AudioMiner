import ssl
import _ssl
import http.client

print(ssl.OPENSSL_VERSION)
print(_ssl.__file__)
print(http.client.HTTPSConnection)