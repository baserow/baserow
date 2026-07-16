#!/usr/bin/env bash
# Generates a minimal, inbound-only mox configuration for the `email-receiver`
# role from BASEROW_INBOUND_EMAIL_* environment variables. Mox receives email
# for {token}@$BASEROW_INBOUND_EMAIL_DOMAIN addresses and POSTs its incoming
# delivery webhook to the Baserow backend, which dispatches the matching
# "Start workflow by email" automation triggers.
#
# The generated config lives inside the email receiver's persistent data
# directory. Mox's message store and webhook retry queue live there too; the
# at-least-once webhook delivery guarantee depends on that directory surviving
# container restarts.
#
# NOTE: mox config files are in 'sconf' format: indentation MUST be tabs.
set -euo pipefail

DATA_DIR="${BASEROW_INBOUND_EMAIL_DATA_DIR:-/baserow/data/mox}"
CONFIG_DIR="$DATA_DIR/config"

DOMAIN="${BASEROW_INBOUND_EMAIL_DOMAIN:?BASEROW_INBOUND_EMAIL_DOMAIN must be set to run the email-receiver}"
WEBHOOK_SECRET="${BASEROW_INBOUND_EMAIL_WEBHOOK_SECRET:?BASEROW_INBOUND_EMAIL_WEBHOOK_SECRET must be set to run the email-receiver}"
WEBHOOK_URL="${BASEROW_INBOUND_EMAIL_WEBHOOK_URL:-http://backend:8000/api/inbound-email/}"
SMTP_HOSTNAME="${BASEROW_INBOUND_EMAIL_SMTP_HOSTNAME:-$DOMAIN}"
SMTP_PORT="${BASEROW_INBOUND_EMAIL_SMTP_PORT:-25}"
TLS_MODE="${BASEROW_INBOUND_EMAIL_TLS_MODE:-self-signed}"
# Mox must be started as root (it binds its sockets as root and then drops
# privileges itself); this is the unprivileged uid it drops to.
MOX_USER="${BASEROW_INBOUND_EMAIL_MOX_USER:-9999}"

mkdir -p "$CONFIG_DIR" "$DATA_DIR/data"

case "$TLS_MODE" in
  self-signed)
    # Sending mail servers use opportunistic STARTTLS and do not validate the
    # certificate, so a self-signed certificate still upgrades inbound
    # connections to TLS. Use `manual` with a real certificate where possible.
    TLS_CERT_FILE="$CONFIG_DIR/selfsigned.crt"
    TLS_KEY_FILE="$CONFIG_DIR/selfsigned.key"
    if [[ ! -f "$TLS_CERT_FILE" || ! -f "$TLS_KEY_FILE" ]]; then
      echo "Generating self-signed TLS certificate for $SMTP_HOSTNAME..."
      MOX_TLS_HOSTNAME="$SMTP_HOSTNAME" \
      MOX_TLS_CERT_FILE="$TLS_CERT_FILE" \
      MOX_TLS_KEY_FILE="$TLS_KEY_FILE" \
      python3 - <<'PYTHON'
import os
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

hostname = os.environ["MOX_TLS_HOSTNAME"]
key = ec.generate_private_key(ec.SECP256R1())
name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
now = datetime.now(timezone.utc)
cert = (
    x509.CertificateBuilder()
    .subject_name(name)
    .issuer_name(name)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now - timedelta(days=1))
    .not_valid_after(now + timedelta(days=3650))
    .add_extension(
        x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False
    )
    .sign(key, hashes.SHA256())
)
with open(os.environ["MOX_TLS_KEY_FILE"], "wb") as f:
    f.write(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
with open(os.environ["MOX_TLS_CERT_FILE"], "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))
PYTHON
    fi
    ;;
  manual)
    TLS_CERT_FILE="${BASEROW_INBOUND_EMAIL_TLS_CERT_FILE:?BASEROW_INBOUND_EMAIL_TLS_CERT_FILE must be set when BASEROW_INBOUND_EMAIL_TLS_MODE=manual}"
    TLS_KEY_FILE="${BASEROW_INBOUND_EMAIL_TLS_KEY_FILE:?BASEROW_INBOUND_EMAIL_TLS_KEY_FILE must be set when BASEROW_INBOUND_EMAIL_TLS_MODE=manual}"
    ;;
  *)
    echo "Unsupported BASEROW_INBOUND_EMAIL_TLS_MODE: $TLS_MODE (expected self-signed or manual)" >&2
    exit 1
    ;;
esac

cat > "$CONFIG_DIR/mox.conf" <<EOF
DataDir: ../data
LogLevel: info
User: $MOX_USER
Hostname: $SMTP_HOSTNAME
Listeners:
	inbound:
		IPs:
			- 0.0.0.0
		TLS:
			KeyCerts:
				-
					CertFile: $TLS_CERT_FILE
					KeyFile: $TLS_KEY_FILE
		SMTP:
			Enabled: true
			Port: $SMTP_PORT
Postmaster:
	Account: inbound
	Mailbox: Inbox
EOF

cat > "$CONFIG_DIR/domains.conf" <<EOF
Domains:
	$DOMAIN: nil
Accounts:
	inbound:
		IncomingWebhook:
			URL: $WEBHOOK_URL
			Authorization: $WEBHOOK_SECRET
		KeepRetiredMessagePeriod: 72h0m0s
		KeepRetiredWebhookPeriod: 72h0m0s
		Domain:
		Destinations:
			@$DOMAIN: nil
		RejectsMailbox: Rejects
		NoFirstTimeSenderDelay: true
EOF

# The unprivileged mox process must be able to write its message store and
# webhook retry queue.
if [[ "$(id -u)" == "0" ]]; then
  chown -R "$MOX_USER:$MOX_USER" "$DATA_DIR"
fi

echo "Mox configuration generated in $CONFIG_DIR"
