from typing import Dict

from django.conf import settings

from baserow.contrib.builder.domains.exceptions import (
    SubDomainHasInvalidDomainName,
    SubDomainNameContainsDot,
)
from baserow.contrib.builder.domains.models import CustomDomain, SubDomain
from baserow.contrib.builder.domains.registries import DomainType


class CustomDomainType(DomainType):
    type = "custom"
    model_class = CustomDomain


class SubDomainType(DomainType):
    type = "sub_domain"
    model_class = SubDomain

    def prepare_values(self, values: Dict) -> Dict:
        domain_name = values.get("domain_name", None)

        if domain_name is not None:
            self._validate_domain_name(domain_name)

        return values

    def _validate_domain_name(self, domain_name: str):
        """
        Checks if the subdomain uses a domain name that is among the available domain
        names defined in settings, and that the part in front of it is a single
        label. The wildcard certificate of an available domain name only covers one
        level, so `foo.bar.example.com` can't be served securely.

        :param domain_name: The name that is being proposed
        :raises SubDomainHasInvalidDomainName: If the domain name is not registered
        :raises SubDomainNameContainsDot: If the part in front of the registered
            domain name contains a dot.
        """

        matching_domains = [
            domain
            for domain in settings.BASEROW_BUILDER_DOMAINS
            if domain_name.endswith(f".{domain}")
        ]

        if not matching_domains:
            raise SubDomainHasInvalidDomainName(domain_name)

        # Multiple available domain names can match, `foo.eu.example.com` ends with
        # both `example.com` and `eu.example.com`, so it's enough if one of them
        # leaves a single label.
        if all("." in domain_name[: -len(domain) - 1] for domain in matching_domains):
            raise SubDomainNameContainsDot(domain_name)
