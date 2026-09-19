def make_mox_payload(rcpt_to, **overrides):
    """
    Builds a realistic mox `webhook.Incoming` JSON payload, as POSTed by mox's
    incoming-delivery webhook, targeting the provided recipient address.
    """

    payload = {
        "Version": 0,
        "From": [{"Name": "Ada Lovelace", "Address": "ada@example.com"}],
        "To": [{"Name": "", "Address": rcpt_to}],
        "CC": [],
        "BCC": [],
        "ReplyTo": [{"Name": "Ada Lovelace", "Address": "ada@example.com"}],
        "Subject": "Hello from Ada",
        "MessageID": "<unique-id-123@example.com>",
        "InReplyTo": "",
        "References": [],
        "Date": "2026-07-15T12:00:00Z",
        "Text": "Hi there,\n\nThis is the plain text body.\n",
        "HTML": "<p>Hi there,</p><p>This is the HTML body.</p>",
        "Structure": {
            "ContentType": "multipart/mixed",
            "ContentTypeParams": {"boundary": "x"},
            "ContentID": "",
            "ContentDisposition": "",
            "Filename": "",
            "DecodedSize": 0,
            "Parts": [
                {
                    "ContentType": "text/plain",
                    "ContentTypeParams": {"charset": "utf-8"},
                    "ContentID": "",
                    "ContentDisposition": "",
                    "Filename": "",
                    "DecodedSize": 45,
                    "Parts": [],
                },
                {
                    "ContentType": "application/pdf",
                    "ContentTypeParams": {},
                    "ContentID": "",
                    "ContentDisposition": "attachment",
                    "Filename": "invoice.pdf",
                    "DecodedSize": 12345,
                    "Parts": [],
                },
            ],
        },
        "Meta": {
            "MsgID": 42,
            "MailFrom": "ada@example.com",
            "MailFromValidated": True,
            "MsgFromValidated": True,
            "RcptTo": rcpt_to,
            "DKIMVerifiedDomains": ["example.com"],
            "RemoteIP": "203.0.113.10",
            "Received": "2026-07-15T12:00:01Z",
            "MailboxName": "Inbox",
            "Automated": False,
        },
    }
    payload.update(overrides)
    return payload
