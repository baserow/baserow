import unicodedata
from typing import Dict

from django.conf import settings

from baserow.contrib.builder.domains.exceptions import (
    SubDomainHasInvalidDomainName,
    SubDomainNameContainsDot,
)
from baserow.contrib.builder.domains.models import CustomDomain, SubDomain
from baserow.contrib.builder.domains.registries import DomainType

# The ideographic full stop isn't changed by the NFKC normalization, but browsers
# treat it as a label separator just like the dot.
LABEL_SEPARATORS = (".", "\u3002")


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
        level, so `foo.bar.example.com` can't be served securely. Unicode characters
        that browsers resolve to a dot, like the fullwidth full stop, count as a dot.

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
        if all(
            self._contains_label_separator(domain_name[: -len(domain) - 1])
            for domain in matching_domains
        ):
            raise SubDomainNameContainsDot(domain_name)

    def _contains_label_separator(self, name: str) -> bool:
        """
        Checks if the name contains a dot, or a Unicode character that is equivalent
        to one in a domain name.

        :param name: The part in front of the available domain name.
        :return: True if the name consists of more than one label.
        """

        normalized_name = unicodedata.normalize("NFKC", name)
        return any(separator in normalized_name for separator in LABEL_SEPARATORS)
