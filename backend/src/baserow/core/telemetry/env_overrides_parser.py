from typing import Dict, NamedTuple, Optional

from loguru import logger
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    DEFAULT_OFF,
    DEFAULT_ON,
    ParentBasedTraceIdRatio,
    Sampler,
)

from .sampling import ForcableTraceIdRatioBased

_KNOWN_SAMPLERS = {
    "always_on": ALWAYS_ON,
    "always_off": ALWAYS_OFF,
    "parentbased_always_on": DEFAULT_ON,
    "parentbased_always_off": DEFAULT_OFF,
    "traceidratio": ForcableTraceIdRatioBased,
    "parentbased_traceidratio": ParentBasedTraceIdRatio,
}


def get_sampler_overrides_from_str(overrides: str) -> Dict[str, Sampler]:
    """
    Given a string in the format of:
     module.name.something=sampler,other.module=other-sampler-with-param@0.5
    this function will parse the string a return a dictionary keyed by the module name
    with values containing setup OTEL Samplers configured according to the string.

    The supported sampler strings are:
        * "always_on"
        * "always_off"
        * "parentbased_always_on"
        * "parentbased_always_off"
        * "traceidratio@{float}"
        * "parentbased_traceidratio@{float}"
    And correspond to the OTEL samplers with the same names, see
    https://opentelemetry-python.readthedocs.io/en/latest/sdk/trace.sampling.html for
    more details.
    """

    overrides = overrides.strip().lower().split(",")
    per_module_sampler_overrides = {}

    for override in overrides:
        module_and_sampler = _try_get_sampler_and_module_from_str(override)
        if module_and_sampler is not None:
            per_module_sampler_overrides[module_and_sampler.module] = (
                module_and_sampler.sampler
            )

    return per_module_sampler_overrides


class ModuleAndSamplerTuple(NamedTuple):
    module: str
    sampler: Sampler


def _try_get_sampler_and_module_from_str(override) -> Optional[ModuleAndSamplerTuple]:
    override = override.strip()
    if not override:
        return None

    # Expect the string to be "module.name=sampler"
    module_and_sampler = override.split("=")
    if len(module_and_sampler) == 2:
        # The string was "module.name=sampler"
        module = module_and_sampler[0]
        raw_sampler_str = module_and_sampler[1]

        # Now parse the sampler part which can be either "sampler_name" or
        # "sampler_name@param"
        sampler_with_optional_param = raw_sampler_str.split("@")
        sampler = sampler_with_optional_param[0]
        try:
            optional_sampler_param = sampler_with_optional_param[1]
        except IndexError:
            optional_sampler_param = None

        generated_sampler = _generate_sampler_from_string_args(
            module, sampler, optional_sampler_param
        )
        if generated_sampler is not None:
            return ModuleAndSamplerTuple(
                module,
                generated_sampler,
            )
    else:
        logger.warning(
            "Found invalid option in "
            "OTEL_PER_MODULE_SAMPLER_OVERRIDES: {}, which had "
            "multiple equals values, skipping.",
            override,
        )


def _generate_sampler_from_string_args(
    module: str, trace_sampler: str, arg: str
) -> Optional[Sampler]:
    if trace_sampler not in _KNOWN_SAMPLERS:
        logger.warning("Couldn't recognize sampler {}.", trace_sampler)
        return None

    if trace_sampler in ("traceidratio", "parentbased_traceidratio"):
        try:
            rate = float(arg)
            sampler = _KNOWN_SAMPLERS[trace_sampler](rate)
        except (ValueError, TypeError):
            logger.warning(
                "Could not convert arg {} for to float it was {}.", trace_sampler, arg
            )
            return None

        logger.info(
            "Instrumentation from module: {} overriden to use sampler {} with param {}",
            module,
            trace_sampler,
            rate,
        )
        return sampler
    else:
        logger.info(
            "Instrumentation from module: {} overriden to use sampler {}",
            module,
            trace_sampler,
        )
        return _KNOWN_SAMPLERS[trace_sampler]
