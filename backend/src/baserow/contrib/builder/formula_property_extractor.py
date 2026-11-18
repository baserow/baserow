from typing import TYPE_CHECKING, Dict, List

from baserow.contrib.builder.data_providers.registries import (
    builder_data_provider_type_registry,
)
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.core.formula.property_extractor import (
    FormulaFieldVisitor as RuntimeFormulaFieldVisitor,
)
from baserow.core.user_sources.user_source_user import UserSourceUser
from baserow.core.utils import merge_dicts_no_duplicates

if TYPE_CHECKING:
    from baserow.contrib.builder.data_sources.models import DataSource
    from baserow.contrib.builder.models import Builder
    from baserow.core.workflow_actions.models import WorkflowAction


class FormulaFieldVisitor(RuntimeFormulaFieldVisitor):
    """Extract Builder formula properties with the shared runtime formula visitor."""

    def __init__(self, **kwargs):
        super().__init__(builder_data_provider_type_registry, **kwargs)


def get_element_property_names(
    elements: List[Element],
    element_map: Dict[str, Element],
) -> Dict[str, Dict[int, List[str]]]:
    """
    Given a list of elements, find its formulas and extract their property names.

    This function will update the results dict. It will only update the
    "external" key, since all builder Elements are user-facing.
    """

    from baserow.contrib.builder.elements.handler import ElementHandler

    results = {}

    for element in elements:
        formula_context = ElementHandler().get_import_context_addition(
            element.parent_element_id, element_map
        )

        results = merge_dicts_no_duplicates(
            results,
            element.get_type().extract_properties(element.specific, **formula_context),
        )

    return {"external": results}


def get_workflow_action_property_names(
    workflow_actions: List["WorkflowAction"],
    element_map: Dict[str, Element],
) -> Dict[str, Dict[int, List[str]]]:
    """
    Given a Page, loop through all of its workflow actions and find its formula
    property names.

    This function will update the results dict. It will update both the
    "internal" and "external" keys.
        - "internal" property names are those that are only needed by the backend.
        - "external" property names are those needed in the frontend.
    """

    from baserow.contrib.builder.elements.handler import ElementHandler
    from baserow.contrib.builder.workflow_actions.workflow_action_types import (
        BuilderWorkflowServiceActionType,
    )

    results = {"internal": {}, "external": {}}

    for workflow_action in workflow_actions:
        formula_context = ElementHandler().get_import_context_addition(
            workflow_action.element_id,
            element_map,
            include_target=workflow_action.event != EventTypes.CHANGE,
        )

        found_properties = workflow_action.get_type().extract_properties(
            workflow_action, **formula_context
        )

        if isinstance(workflow_action.get_type(), BuilderWorkflowServiceActionType):
            # Action using service are internal use only
            results["internal"] = merge_dicts_no_duplicates(
                results["internal"], found_properties
            )
        else:
            results["external"] = merge_dicts_no_duplicates(
                results["external"], found_properties
            )

    return results


def get_data_source_property_names(
    data_sources: List["DataSource"],
) -> Dict[str, Dict[int, List[str]]]:
    """
    Given a Page, loop through all of its data sources. Find all related
    services and return the property names of their formulas.

    This function will update the results dict. It will only update the
    "internal" keys, since data source property names are only required by
    the backend.
    """

    results = {}

    for data_source in data_sources:
        results = merge_dicts_no_duplicates(
            results,
            data_source.extract_properties(data_source),
        )

    return {"internal": results}


def get_builder_used_property_names(
    user: UserSourceUser, builder: "Builder"
) -> Dict[str, Dict[int, List[str]]]:
    """
    Given a UserSourceUser and a Builder, return all property names used in the all the
    pages.

    This involves looping over all Elements, Workflow Actions, and Data Sources
    in the Builder.

    The property names are categorized by "internal" and "external" property names.

    Internal property names are those property names that the frontend does
    not require. By excluding these property names, we improve the security of
    the AB.

    External property names are those property names used explicitly by
    Elements or certain Workflow Actions in the Page.

    If the user isn't allowed to view any Elements due to permissions, or
    if the Elements have no formulas, no property names will be returned.
    """

    from baserow.contrib.builder.data_sources.service import DataSourceService
    from baserow.contrib.builder.elements.service import ElementService
    from baserow.contrib.builder.workflow_actions.service import (
        BuilderWorkflowActionService,
    )

    # We query the data source first to populate the data source cache
    data_sources = DataSourceService().get_builder_data_sources(
        user, builder, with_cache=True
    )

    elements = list(ElementService().get_builder_elements(user, builder))
    element_map = {e.id: e for e in elements}

    element_results = get_element_property_names(elements, element_map)

    ds_results = get_data_source_property_names(data_sources)

    workflow_actions = BuilderWorkflowActionService().get_builder_workflow_actions(
        user, builder
    )
    wa_results = get_workflow_action_property_names(workflow_actions, element_map)

    results = {
        "internal": merge_dicts_no_duplicates(
            wa_results["internal"], ds_results["internal"]
        ),
        "external": merge_dicts_no_duplicates(
            wa_results["external"], element_results["external"]
        ),
    }

    all_property_names = merge_dicts_no_duplicates(
        results["internal"],
        results["external"],
    )
    results["all"] = {key: sorted(value) for key, value in all_property_names.items()}
    results["internal"] = {
        key: sorted(value) for key, value in results["internal"].items()
    }
    results["external"] = {
        key: sorted(value) for key, value in results["external"].items()
    }

    return results
