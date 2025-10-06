#!/usr/bin/env python3
"""
Voice2Text HTTPS Mobile Server
==============================
HTTPS-enabled server for iOS Safari microphone access compatibility.
"""

import ssl
import os
from pathlib import Path

# Import your existing server class
import sys
sys.path.append('.')
from v2t_mobile_server import Voice2TextMobileServer

def create_ssl_context():
    """Generate SSL context for HTTPS operation."""
    # Create SSL context with self-signed certificate
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    
    # For development/local use, we'll use a simple self-signed approach
    # This will show security warnings but enables microphone access
    cert_file = Path('voice2text.crt')
    key_file = Path('voice2text.key')
    
    if not cert_file.exists() or not key_file.exists():
        print("🔧 Generating SSL certificate for HTTPS operation...")
        generate_self_signed_cert()
    
    context.load_cert_chain(cert_file, key_file)
    return context

def generate_self_signed_cert():
    """Generate self-signed certificate for local HTTPS."""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
        import ipaddress
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Local"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Voice2Text"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Voice2Text Local"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.now(datetime.UTC)
        ).not_valid_after(
            datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                x509.IPAddress(ipaddress.IPv4Address("192.168.68.66")),  # Your actual network IP
                x509.IPAddress(ipaddress.IPv4Address("192.168.1.1")),
                x509.IPAddress(ipaddress.IPv4Address("192.168.0.1")),
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Write certificate and key to files
        with open("voice2text.crt", "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        with open("voice2text.key", "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        print("✅ SSL certificate generated successfully")
        
    except ImportError:
        print("❌ Cryptography library required for SSL certificate generation")
        print("💡 Install with: pip install cryptography")
        print("📋 Alternative: Use manual certificate generation or HTTP fallback")
        return False
    
    return True

def main():
    """Launch HTTPS-enabled mobile server."""
    try:
        # Generate SSL context
        ssl_context = create_ssl_context()
        
        # Initialize and start server with HTTPS
        server = Voice2TextMobileServer()
        server.run_server(host='0.0.0.0', port=5443, ssl_context=ssl_context)
        
    except Exception as e:
        print(f"❌ HTTPS server startup failed: {e}")
        print("🔄 Attempting HTTP fallback...")
        
        # Fallback to HTTP server
        server = Voice2TextMobileServer()
        server.run_server(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    main()