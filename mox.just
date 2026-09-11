# Mox mail server recipes for local development of the "Start workflow by email"
# automation trigger. Delegated to from the root justfile as `just mox <recipe>`.
#
# Typical flow (backend running natively with `just dev`):
#   just mox up               # run the receiver in Docker (foreground, Ctrl+C to stop)
#   just mox address          # print the trigger's inbound address (copy from here)
#   just mox send <address>   # send a test email through mox
#
# `just mox up` runs the same `email-receiver` role as production from the
# backend dev image (compose profile "mox"), so nothing has to be installed on
# the host. It posts webhooks to the natively running backend through
# host.docker.internal. Once BASEROW_INBOUND_EMAIL_DOMAIN and
# BASEROW_INBOUND_EMAIL_WEBHOOK_SECRET are set in .env.local, `just dev up`
# starts the receiver automatically (`just mox up -d`) and `just dev stop`
# stops it. The fully dockerised stack does the same from .env.docker-dev.
#
# Native alternative, if you have the `mox` binary installed (brew install mox):
#   just mox init             # one-time (or after a reset): generate + validate config
#   just mox up-native        # run `mox localserve` (foreground, Ctrl+C to stop)

set unstable := true

# Where the throwaway mox config + message store live. A short path is required:
# mox's unix control socket hits the macOS ~104 char sun_path limit otherwise.
MOX_DIR := "/tmp/baserow-mox"

# Host port the receiver's SMTP listener is published on. Deliberately 2025, not
# localserve's default 1025, which collides with MailHog in the standard Baserow
# dev stack. Override with BASEROW_INBOUND_EMAIL_HOST_SMTP_PORT if 2025 is taken.
MOX_SMTP_PORT := env_var_or_default("BASEROW_INBOUND_EMAIL_HOST_SMTP_PORT", "2025")

# Load the repo-root .env.local so the mox config uses the SAME inbound domain
# and webhook secret the backend reads, keeping the two sides in sync.
_load_env := 'set -a; [ -f .env.local ] && . ./.env.local; set +a'

# The dev compose stack; the receiver lives in docker-compose.dev.yml behind the
# "mox" profile.
_dc := 'docker compose --env-file .env.docker-dev -f docker-compose.yml -f docker-compose.dev.yml'

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

# Ensure .env.local carries the two variables both the backend and the receiver
# need, generating a secret if absent. Appended only when the key is missing.
_ensure-env:
    #!/usr/bin/env bash
    set -euo pipefail
    {{ _load_env }}
    if [ -z "${BASEROW_INBOUND_EMAIL_DOMAIN:-}" ]; then
        echo "BASEROW_INBOUND_EMAIL_DOMAIN=inbound.baserow.local" >> .env.local
        echo "  + added BASEROW_INBOUND_EMAIL_DOMAIN=inbound.baserow.local to .env.local"
    fi
    if [ -z "${BASEROW_INBOUND_EMAIL_WEBHOOK_SECRET:-}" ]; then
        echo "BASEROW_INBOUND_EMAIL_WEBHOOK_SECRET=$(openssl rand -hex 16)" >> .env.local
        echo "  + added BASEROW_INBOUND_EMAIL_WEBHOOK_SECRET (generated) to .env.local"
    fi

# Run the receiver in Docker from the backend dev image, next to a backend that
# runs natively on the host. Builds the dev image on first use. Pass -d to run
# detached (used by `just dev up`).
[doc("Run the mox receiver in Docker (foreground, Ctrl+C to stop; -d to detach)")]
up *FLAGS:
    #!/usr/bin/env bash
    set -euo pipefail
    DETACHED=false
    for flag in {{ FLAGS }}; do
        [ "$flag" = "-d" ] && DETACHED=true
    done
    just --justfile mox.just _ensure-env
    {{ _load_env }}
    if [ ! -f .env.docker-dev ] && [ -f .env.docker-dev.example ]; then
        cp .env.docker-dev.example .env.docker-dev
    fi
    # Build args for the dev image, as `just dc-dev` sets them.
    if [[ -z "${UID:-}" ]]; then UID=$(id -u); fi; export UID
    if [[ -z "${GID:-}" ]]; then GID=$(id -g); fi; export GID
    # The container reaches the host's backend through Docker's host gateway.
    BACKEND_URL="${PUBLIC_BACKEND_URL:-http://localhost:8000}"
    BACKEND_URL="${BACKEND_URL/localhost/host.docker.internal}"
    BACKEND_URL="${BACKEND_URL/127.0.0.1/host.docker.internal}"
    export BASEROW_INBOUND_EMAIL_WEBHOOK_URL="${BASEROW_INBOUND_EMAIL_WEBHOOK_URL:-${BACKEND_URL%/}/api/inbound-email/}"
    export BASEROW_INBOUND_EMAIL_HOST_SMTP_PORT="{{ MOX_SMTP_PORT }}"
    export BASEROW_INBOUND_EMAIL_HOST_PUBLISH_IP="${BASEROW_HOST_PUBLISH_IP:-127.0.0.1}"
    export BASEROW_INBOUND_EMAIL_DOMAIN BASEROW_INBOUND_EMAIL_WEBHOOK_SECRET
    if ! docker image inspect baserow_backend:dev >/dev/null 2>&1; then
        echo "Building the backend dev image (first run only, takes a few minutes)..."
        {{ _dc }} build email-receiver
    fi
    if [ "$DETACHED" = true ]; then
        {{ _dc }} --profile mox up -d --no-deps email-receiver
        echo "Mox receiver started for '$BASEROW_INBOUND_EMAIL_DOMAIN' (SMTP on localhost:{{ MOX_SMTP_PORT }}, webhooks to $BASEROW_INBOUND_EMAIL_WEBHOOK_URL). Logs: docker logs -f baserow-email-receiver-1"
    else
        echo "Starting the mox receiver for '$BASEROW_INBOUND_EMAIL_DOMAIN' (SMTP on localhost:{{ MOX_SMTP_PORT }}, webhooks to $BASEROW_INBOUND_EMAIL_WEBHOOK_URL). Press Ctrl+C to stop."
        exec {{ _dc }} --profile mox up --no-deps email-receiver
    fi

# Wipe {{ MOX_DIR }} and generate a fresh, validated config for the native
# `mox localserve` flow. Safe to re-run: it always starts from a clean directory.
[doc("Native flow: wipe, regenerate and validate the local mox config")]
init: _check-binary
    #!/usr/bin/env bash
    set -euo pipefail
    just --justfile mox.just _ensure-env
    {{ _load_env }}
    DOMAIN="$BASEROW_INBOUND_EMAIL_DOMAIN"
    SECRET="$BASEROW_INBOUND_EMAIL_WEBHOOK_SECRET"
    WEBHOOK_URL="${BASEROW_INBOUND_EMAIL_WEBHOOK_URL:-}"
    if [ -z "$WEBHOOK_URL" ]; then
        : "${PUBLIC_BACKEND_URL:?Set PUBLIC_BACKEND_URL in .env.local}"
        WEBHOOK_URL="${PUBLIC_BACKEND_URL%/}/api/inbound-email/"
    fi

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
    echo "  just mox up-native                # start the native mail server"
    echo "  just mox address                  # copy the trigger's inbound address"
    echo "  just mox send <address>           # send a test email"

# Run the native mox mail server in the foreground (Ctrl+C to stop).
# Auto-initialises the config if it does not exist yet.
[doc("Native flow: run `mox localserve` (foreground, Ctrl+C to stop)")]
up-native: _check-binary
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -f "{{ MOX_DIR }}/mox.conf" ]; then
        echo "No mox config found, running 'just mox init' first..."
        just --justfile mox.just init
    fi
    echo "Starting mox (SMTP on localhost:{{ MOX_SMTP_PORT }}). Press Ctrl+C to stop."
    exec mox localserve -dir "{{ MOX_DIR }}"

# Stop and remove the Docker receiver only (used by `just dev stop`). Prints
# nothing when it is not running.
_down-docker:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -f .env.docker-dev ] && {{ _dc }} --profile mox ps -q email-receiver 2>/dev/null | grep -q .; then
        {{ _dc }} --profile mox rm -sf email-receiver >/dev/null 2>&1
        echo "Stopped the mox receiver container."
    fi

# Stop the receiver, whether it runs as the Docker service or as a
# (backgrounded) native `mox localserve`.
[doc("Stop the mox receiver (Docker or native)")]
down:
    #!/usr/bin/env bash
    set -euo pipefail
    stopped=0
    if [ -n "$(just --justfile mox.just _down-docker)" ]; then
        echo "Stopped the mox receiver container."
        stopped=1
    fi
    if pkill -f "mox localserve -dir {{ MOX_DIR }}"; then
        echo "Stopped native mox localserve."
        stopped=1
    fi
    [ "$stopped" = 1 ] || echo "No running mox receiver found."

# Validate the generated mox config.
[doc("Native flow: validate the generated mox config")]
test:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -f "{{ MOX_DIR }}/mox.conf" ]; then
        echo "No mox config found. Run 'just mox init' first." >&2
        exit 1
    fi
    MOXCONF="{{ MOX_DIR }}/mox.conf" mox config test

# Remove the mox config and message store entirely.
[doc("Native flow: remove the mox config and message store")]
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
        # The draft is reached through the `test-` prefixed address.
        addr = s.email_address if s.is_public else s.test_email_address
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
