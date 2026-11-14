from django.conf import settings


class DomainDoesNotExist(Exception):
    """Raised when trying to get a domain that doesn't exist."""


class DomainNotInBuilder(Exception):
    """Raised when trying to get a domain that does not belong to the correct builder"""

    def __init__(self, domain_id=None, *args, **kwargs):
        self.domain_id = domain_id
        super().__init__(
            f"The domain {domain_id} does not belong to the builder.",
            *args,
            **kwargs,
        )


class DomainNameNotUniqueError(Exception):
    """Raised when trying to set a domain name that already exists"""

    def __init__(self, domain_name, *args, **kwargs):
        self.domain_name = domain_name
        super().__init__(
            f"The domain name {domain_name} already exists", *args, **kwargs
        )


class SubDomainHasInvalidDomainName(Exception):
    """Raised when a subdomain is using an invalid domain name"""

    def __init__(self, domain_name, *args, **kwargs):
        self.domain_name = domain_name
        self.available_domain_names = settings.BASEROW_BUILDER_DOMAINS
        super().__init__(
            f"The subdomain {domain_name} has an invalid domain name, you can only use "
            f"{self.available_domain_names}",
            *args,
            **kwargs,
        )


class SubDomainNameContainsDot(Exception):
    """Raised when the name in front of the subdomain's domain name contains a dot"""

    def __init__(self, domain_name, *args, **kwargs):
        self.domain_name = domain_name
        super().__init__(
            f"The subdomain {domain_name} can't contain a dot in front of the domain "
            f"name.",
            *args,
            **kwargs,
        )
