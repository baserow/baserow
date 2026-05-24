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
