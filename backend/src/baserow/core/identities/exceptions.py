class IdentityDoesNotExist(Exception):
    pass


class IdentityRoleDoesNotExist(Exception):
    pass


class IdentityCannotBeScoped(Exception):
    """
    Raised when an identity can't be given access to only some applications: it
    already has more access, or none of the roles it should get can be given.
    """
