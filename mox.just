# Mox mail server recipes for local development of the "Start workflow by email"
# automation trigger. Delegated to from the root justfile as `just mox <recipe>`.
#
# Typical flow:
#   just mox init      # one-time (or after a reset): generate + validate config
#   just mox up        # run the mail server (foreground, Ctrl+C to stop)
#   just mox address   # print the trigger's inbound address (copy from here)
#   just mox send <address>   # send a test email through mox

set unstable := true

# Where the throwaway mox config + message store live. A short path is required:
# mox's unix control socket hits the macOS ~104 char sun_path limit otherwise.
MOX_DIR := "/tmp/baserow-mox"

# SMTP port mox listens on. Deliberately 2025, not localserve's default 1025,
# which collides with MailHog in the standard Baserow dev stack.
MOX_SMTP_PORT := "2025"

# Load the repo-root .env.local so the mox config uses the SAME inbound domain
# and webhook secret the backend reads, keeping the two sides in sync.
_load_env := 'set -a; [ -f .env.local ] && . ./.env.local; set +a'

# Show the available mox recipes.
[doc("List mox recipes")]
default:
    @just --justfile mox.just --list

# Check the mox binary is installed, with install hints if not.
_check-binary:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v mox >/dev/null 2>&1; then
        echo "error: 'mox' is not installed or not on PATH." >&2
        echo "  macOS:  brew install mox" >&2
        echo "  other:  go install github.com/mjl-/mox@latest  (needs Go)" >&2
        echo "  docs:   https://github.com/mjl-/mox" >&2
        exit 1
    fi

# Wipe {{ MOX_DIR }} and generate a fresh, validated mox config for the inbound
# email trigger. Reads the inbound domain and webhook secret from .env.local,
# adding sensible defaults there if they are missing so both mox and the backend
# agree. Safe to re-run: it always starts from a clean directory.
[doc("Wipe, regenerate and validate the local mox config")]
init: _check-binary
    #!/usr/bin/env bash
    set -euo pipefail
    {{ _load_env }}

    # Ensure .env.local carries the two variables the backend needs, generating
    # a secret if absent. Appended only when the key is not already present.
    DOMAIN="${BASEROW_INBOUND_EMAIL_DOMAIN:-}"
    SECRET="${BASEROW_INBOUND_EMAIL_WEBHOOK_SECRET:-}"
    if [ -z "$DOMAIN" ]; then
        DOMAIN="inbound.baserow.local"
        if ! grep -q '^BASEROW_INBOUND_EMAIL_DOMAIN=' .env.local 2>/dev/null; then
            echo "BASEROW_INBOUND_EMAIL_DOMAIN=$DOMAIN" >> .env.local
            echo "  + added BASEROW_INBOUND_EMAIL_DOMAIN=$DOMAIN to .env.local"
        fi
    fi
    if [ -z "$SECRET" ]; then
        SECRET="$(openssl rand -hex 16)"
        if ! grep -q '^BASEROW_INBOUND_EMAIL_WEBHOOK_SECRET=' .env.local 2>/dev/null; then
            echo "BASEROW_INBOUND_EMAIL_WEBHOOK_SECRET=$SECRET" >> .env.local
            echo "  + added BASEROW_INBOUND_EMAIL_WEBHOOK_SECRET (generated) to .env.local"
        fi
    fi
    WEBHOOK_URL="${BASEROW_INBOUND_EMAIL_WEBHOOK_URL:-http://localhost:8000/api/inbound-email/}"

    echo "Generating mox config in {{ MOX_DIR }} for domain '$DOMAIN'..."
    rm -rf "{{ MOX_DIR }}"
    mkdir -p "{{ MOX_DIR }}"
    mox localserve -dir "{{ MOX_DIR }}" -initonly >/dev/null

    # Patch the generated config: SMTP port, inbound domain, catch-all
    # destination, and the incoming webhook pointing at the backend.
    MOX_DIR="{{ MOX_DIR }}" \
    MOX_SMTP_PORT="{{ MOX_SMTP_PORT }}" \
    INBOUND_DOMAIN="$DOMAIN" \
    WEBHOOK_URL="$WEBHOOK_URL" \
    WEBHOOK_SECRET="$SECRET" \
    python3 <<'PY'
    import os

    mox_dir = os.environ["MOX_DIR"]
    smtp_port = os.environ["MOX_SMTP_PORT"]
    domain = os.environ["INBOUND_DOMAIN"]
    url = os.environ["WEBHOOK_URL"]
    secret = os.environ["WEBHOOK_SECRET"]

    # mox.conf: move the SMTP listener off localserve's default 1025.
    conf_path = os.path.join(mox_dir, "mox.conf")
    conf = open(conf_path).read()
    old_port = "Port: 1025\n"
    assert conf.count(old_port) == 1, f"expected one SMTP Port: 1025, found {conf.count(old_port)}"
    conf = conf.replace(old_port, f"Port: {smtp_port}\n")
    open(conf_path, "w").write(conf)

    # domains.conf: add the inbound domain, a catch-all destination, and the
    # incoming webhook. sconf is tab-indented and orders IncomingWebhook before
    # the KeepRetired* account fields, so it goes in as the first account field.
    dom_path = os.path.join(mox_dir, "domains.conf")
    dom = open(dom_path).read()

    old = "Domains:\n\tlocalhost:\n"
    new = (
        "Domains:\n"
        f"\t{domain}:\n"
        "\t\tLocalpartCatchallSeparator: +\n"
        "\tlocalhost:\n"
    )
    assert dom.count(old) == 1, "domains anchor not found"
    dom = dom.replace(old, new)

    old = "Accounts:\n\tmox:\n\n"
    new = (
        "Accounts:\n\tmox:\n\n"
        "\t\tIncomingWebhook:\n"
        f"\t\t\tURL: {url}\n"
        f"\t\t\tAuthorization: {secret}\n\n"
    )
    assert dom.count(old) == 1, "account anchor not found"
    dom = dom.replace(old, new)

    old = "\t\tDestinations:\n\t\t\tmox@localhost: nil\n"
    new = (
        "\t\tDestinations:\n\t\t\tmox@localhost: nil\n"
        f"\t\t\t@{domain}: nil\n"
    )
    assert dom.count(old) == 1, "destinations anchor not found"
    dom = dom.replace(old, new)

    # Remove the account's JunkFilter block (optional in sconf) so localserve
    # stops rejecting small test emails as "junk-content-strict" (a fresh
    # account has an untrained filter and rejects almost everything).
    import re

    dom, removed = re.subn(
        r"\t\tJunkFilter:\n(?:.*\n)*?(?=\t\t# Do not apply a delay)", "", dom
    )
    assert removed == 1, "JunkFilter block not found"

    open(dom_path, "w").write(dom)
    print("  + patched mox.conf and domains.conf")
    PY

    just --justfile mox.just test
    echo ""
    echo "Mox is configured. Next:"
    echo "  just mox up                       # start the mail server"
    echo "  just mox address                  # copy the trigger's inbound address"
    echo "  just mox send <address>           # send a test email"

# Run the mox mail server in the foreground (Ctrl+C to stop). Auto-initialises
# the config if it does not exist yet.
[doc("Run the mox mail server (foreground, Ctrl+C to stop)")]
up: _check-binary
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -f "{{ MOX_DIR }}/mox.conf" ]; then
        echo "No mox config found, running 'just mox init' first..."
        just --justfile mox.just init
    fi
    echo "Starting mox (SMTP on localhost:{{ MOX_SMTP_PORT }}). Press Ctrl+C to stop."
    exec mox localserve -dir "{{ MOX_DIR }}"

# Stop a running (e.g. backgrounded) mox localserve for this directory.
[doc("Stop a running mox localserve")]
down:
    #!/usr/bin/env bash
    set -euo pipefail
    if pkill -f "mox localserve -dir {{ MOX_DIR }}"; then
        echo "Stopped mox localserve."
    else
        echo "No running 'mox localserve -dir {{ MOX_DIR }}' process found."
    fi

# Validate the generated mox config.
[doc("Validate the generated mox config")]
test:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -f "{{ MOX_DIR }}/mox.conf" ]; then
        echo "No mox config found. Run 'just mox init' first." >&2
        exit 1
    fi
    MOXCONF="{{ MOX_DIR }}/mox.conf" mox config test

# Remove the mox config and message store entirely.
[doc("Remove the mox config and message store")]
clean:
    #!/usr/bin/env bash
    set -euo pipefail
    rm -rf "{{ MOX_DIR }}"
    echo "Removed {{ MOX_DIR }}."

# Print the inbound email addresses of all configured trigger services, so you
# can copy one instead of hunting for it in the UI.
[doc("Print configured inbound trigger addresses")]
address:
    #!/usr/bin/env bash
    set -euo pipefail
    cd backend
    just manage shell <<'PY' 2>/dev/null | grep '@' || echo "No configured inbound email trigger services found (create one in the UI, or check BASEROW_INBOUND_EMAIL_DOMAIN)."
    from baserow.contrib.integrations.core.models import CoreInboundEmailTriggerService
    for s in CoreInboundEmailTriggerService.objects.all():
        addr = s.email_address
        if addr:
            print(f"{addr}  (service {s.id}, {'published' if s.is_public else 'draft'})")
    PY

# Send a test email through mox to the given trigger address. Uses a fresh
# Message-ID each time so it never trips the duplicate-delivery guard. The
# subject is variadic, so trailing words are used as-is without quoting.
# Usage: just mox send <address> [subject words...]
[doc("Send a test email: just mox send <address> [subject words...]")]
send ADDRESS *SUBJECT:
    #!/usr/bin/env bash
    set -euo pipefail
    SUBJECT="{{ SUBJECT }}"
    [ -z "$SUBJECT" ] && SUBJECT="Test email from 'just mox send'"
    if ! (exec 3<>"/dev/tcp/127.0.0.1/{{ MOX_SMTP_PORT }}") 2>/dev/null; then
        echo "error: nothing is listening on localhost:{{ MOX_SMTP_PORT }}. Is mox running? Start it with: just mox up" >&2
        exit 1
    fi
    MOX_SMTP_PORT="{{ MOX_SMTP_PORT }}" \
    TO_ADDRESS="{{ ADDRESS }}" \
    SUBJECT="$SUBJECT" \
    python3 <<'PY'
    import os, smtplib, time
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "Ada Lovelace <mox@localhost>"  # must be @localhost for mox
    msg["To"] = os.environ["TO_ADDRESS"]
    msg["Subject"] = os.environ["SUBJECT"]
    msg["Message-ID"] = f"<{time.time_ns()}.{os.getpid()}@localhost>"
    msg.set_content("This is the plain text body sent through local mox.")
    msg.add_alternative(
        "<p>This is the <strong>HTML body</strong> sent through local mox.</p>",
        subtype="html",
    )

    port = int(os.environ["MOX_SMTP_PORT"])
    with smtplib.SMTP("localhost", port) as smtp:
        smtp.send_message(msg)
    print(f"Sent to {msg['To']} via localhost:{port}")
    PY
