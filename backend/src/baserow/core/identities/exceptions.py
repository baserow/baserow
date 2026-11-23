class IdentityDoesNotExist(Exception):
    pass


class IdentityRoleDoesNotExist(Exception):
    pass


class IdentityCannotBeScoped(Exception):
    """
    Raised when an identity can't be given access to only some applications,
    because it already has more access.
    """
