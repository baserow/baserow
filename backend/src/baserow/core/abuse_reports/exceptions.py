from baserow.core.exceptions import (
    InstanceTypeAlreadyRegistered,
    InstanceTypeDoesNotExist,
)


class AbuseReportingDisabledException(Exception):
    """Raised when reporting abuse has been disabled by the instance admin."""


class AbuseReportResourceTypeDoesNotExist(InstanceTypeDoesNotExist):
    pass


class AbuseReportResourceTypeAlreadyRegistered(InstanceTypeAlreadyRegistered):
    pass
