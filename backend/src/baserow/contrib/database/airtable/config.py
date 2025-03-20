import dataclasses
from typing import Optional


@dataclasses.dataclass
class AirtableImportConfig:
    skip_files: bool = False
    """
    Indicates whether the files should not be downloaded and included in the
    config. This can significantly improve the improvements.
    """

    session: Optional[str] = None
    """
    A session cookie can optionally be provided if the publicly shared base can only be
    accessed authenticated.
    """

    session_signature: Optional[str] = None
    """
    If a session is provided, then the matching signature must be provided as well.
    """

    def get_session_cookies(self):
        cookies = {}
        if self.session:
            cookies["__Host-airtable-session"] = self.session
        if self.session_signature:
            cookies["__Host-airtable-session.sig"] = self.session_signature
        return cookies
