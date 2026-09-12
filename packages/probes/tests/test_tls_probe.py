"""Exercises run_tls against a real local TLS socket (127.0.0.1, a throwaway
self-signed cert) rather than any real third-party host — still "no live
third-party targets," just a real handshake against a fixture we control."""

import datetime
import socket
import ssl
import threading

import pytest
from vigilo_probes.tls_probe import run_tls


def _generate_self_signed_cert(tmp_path, common_name: str = "localhost"):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(common_name)]), critical=False)
        .sign(key, hashes.SHA256())
    )

    key_path = tmp_path / "key.pem"
    cert_path = tmp_path / "cert.pem"
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return str(cert_path), str(key_path)


@pytest.fixture
def tls_server(tmp_path):
    pytest.importorskip("cryptography")
    cert_path, key_path = _generate_self_signed_cert(tmp_path)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)

    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw_sock.bind(("127.0.0.1", 0))
    raw_sock.listen(1)
    port = raw_sock.getsockname()[1]
    stop = threading.Event()

    def serve():
        raw_sock.settimeout(0.2)
        while not stop.is_set():
            try:
                client_sock, _ = raw_sock.accept()
            except TimeoutError:
                continue
            try:
                with context.wrap_socket(client_sock, server_side=True) as tls_client:
                    tls_client.recv(1024)
            except (ssl.SSLError, OSError):
                pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield port, cert_path
    stop.set()
    thread.join(timeout=1)
    raw_sock.close()


def test_run_tls_against_untrusted_self_signed_cert_is_denied(tls_server):
    port, _cert_path = tls_server
    # Default context has no reason to trust our throwaway CA, so this must
    # fail verification — exactly like a real self-signed cert in the wild.
    obs = run_tls("localhost", "127.0.0.1", port)

    assert obs.attempted is True
    assert obs.verified is False
    assert obs.verify_error is not None
    assert obs.protocol_version is None
    assert obs.cert_subject is None


def test_run_tls_against_unreachable_host_is_denied_not_raised():
    obs = run_tls("localhost", "127.0.0.1", 1)  # port 0/1 — nothing listens
    assert obs.attempted is True
    assert obs.verified is False
    assert obs.verify_error is not None
