from dataclasses import dataclass


@dataclass
class RateLimit:
    """
    Represents the number of calls over
    a period for the purpose of rate limiting.
    """

    period_in_seconds: int
    number_of_calls: int

    @staticmethod
    def from_string(rate: str):
        """
        :param rate: String in the format of 'calls/period'.
            Period can be in 's' seconds, 'm' minutes, or 'h' hours.
        """

        try:
            calls, period = rate.split("/")
            calls = int(calls)
            if calls <= 0:
                raise ValueError(
                    "The number of calls provided has to be a positive integer"
                )
            period_in_seconds = {"s": 1, "m": 60, "h": 3600}[period]
            return RateLimit(period_in_seconds=period_in_seconds, number_of_calls=calls)
        except Exception as ex:
            raise ValueError(
                "Provide a valid rate limit value (number of calls/period). The "
                "number of calls should be a positive integer and the period one of "
                "supported period values ('s','m', or 'h')"
            ) from ex


@dataclass
class RunLimit:
    """
    Represents a limit on the number of runs that can be executed
    concurrently or within a time period.
    """

    max_concurrent: int
    max_per_period: int = 0
    period_in_seconds: int = 3600

    def is_within_limit(self, current_count: int) -> bool:
        """Check if the current count is within the limit."""
        return current_count < self.max_concurrent

    @staticmethod
    def from_env(max_concurrent_var: str, max_per_period_var: str = None):
        """
        Create a RunLimit from environment variables.

        :param max_concurrent_var: Env var name for max concurrent runs
        :param max_per_period_var: Env var name for max runs per period (optional)
        """
        import os

        max_concurrent = int(os.getenv(max_concurrent_var, 10))
        max_per_period = 0

        if max_per_period_var:
            max_per_period = int(os.getenv(max_per_period_var, 0))

        return RunLimit(
            max_concurrent=max_concurrent,
            max_per_period=max_per_period
        )
