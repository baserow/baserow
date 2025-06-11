from typing import Dict, List

from baserow.contrib.builder.types import BuilderDict


class BuilderCustomCodeDict(BuilderDict):
    scripts: List[Dict]
    custom_code: Dict
