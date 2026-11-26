from django.conf import settings


def preview_restricts_author_code() -> bool:
    """
    Whether code written by an application's editors, such as custom JavaScript
    and head HTML, is kept out of the application preview.

    Cookies are scoped by hostname, not port, so code running in a preview on
    the editor's hostname can read the editor's cookies, including the user's
    token. Such code only runs there when the instance explicitly relaxes this.
    An unknown hostname counts as shared.
    """

    shares_editor_hostname = (
        settings.BUILDER_PREVIEW_HOSTNAME is None
        or settings.PUBLIC_WEB_FRONTEND_HOSTNAME is None
        or settings.BUILDER_PREVIEW_HOSTNAME == settings.PUBLIC_WEB_FRONTEND_HOSTNAME
    )
    return (
        shares_editor_hostname and not settings.BUILDER_DANGEROUS_RELAX_PREVIEW_SECURITY
    )
