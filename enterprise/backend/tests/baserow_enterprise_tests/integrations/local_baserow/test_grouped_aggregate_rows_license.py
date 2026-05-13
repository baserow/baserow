from django.http import HttpRequest
from django.test import override_settings

import pytest

from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.dashboard.data_sources.dispatch_context import (
    DashboardDispatchContext,
)
from baserow.contrib.dashboard.data_sources.service import DashboardDataSourceService
from baserow.core.services.registries import service_type_registry
from baserow_enterprise.features import BUILDER_GROUPED_AGGREGATE_ROWS
from baserow_enterprise.license_types import (
    AdvancedLicenseType,
    EnterpriseLicenseType,
    EnterpriseWithoutSupportLicenseType,
)
from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowGroupedAggregateRows,
)
from baserow_premium.license.exceptions import FeaturesNotAvailableError


def test_grouped_aggregate_rows_data_source_feature_is_enterprise_only():
    assert BUILDER_GROUPED_AGGREGATE_ROWS not in AdvancedLicenseType.features
    assert (
        BUILDER_GROUPED_AGGREGATE_ROWS in EnterpriseWithoutSupportLicenseType.features
    )
    assert BUILDER_GROUPED_AGGREGATE_ROWS in EnterpriseLicenseType.features


@pytest.mark.django_db
def test_grouped_aggregate_rows_data_source_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    page = enterprise_data_fixture.create_builder_page(user=user)
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")

    enterprise_data_fixture.delete_all_licenses()

    assert service_type.is_deactivated(page.builder.workspace)

    with pytest.raises(FeaturesNotAvailableError):
        DataSourceService().create_data_source(
            user, page=page, service_type=service_type
        )

    with override_settings(DEBUG=True):
        enterprise_data_fixture.enable_enterprise()
        assert not service_type.is_deactivated(page.builder.workspace)


@pytest.mark.django_db
def test_grouped_aggregate_rows_data_source_update_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    page = enterprise_data_fixture.create_builder_page(user=user)
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")

    with override_settings(DEBUG=True):
        enterprise_data_fixture.enable_enterprise()
        data_source = DataSourceService().create_data_source(
            user, page=page, service_type=service_type
        )

    enterprise_data_fixture.delete_all_licenses()

    with pytest.raises(FeaturesNotAvailableError):
        DataSourceService().update_data_source(
            user, data_source, service_type=service_type
        )


@pytest.mark.django_db
def test_grouped_aggregate_rows_data_source_dispatch_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    page = enterprise_data_fixture.create_builder_page(user=user)

    with override_settings(DEBUG=True):
        enterprise_data_fixture.enable_enterprise()
        service = enterprise_data_fixture.create_service(
            LocalBaserowGroupedAggregateRows,
            integration_args={"application": page.builder},
        )
        data_source = enterprise_data_fixture.create_builder_data_source(
            page=page, service=service
        )

    enterprise_data_fixture.delete_all_licenses()

    dispatch_context = BuilderDispatchContext(
        HttpRequest(), page, only_expose_public_allowed_properties=False
    )
    with pytest.raises(FeaturesNotAvailableError):
        DataSourceService().dispatch_data_source(user, data_source, dispatch_context)


@pytest.mark.django_db
def test_grouped_aggregate_rows_dashboard_data_source_dispatch_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    dashboard = enterprise_data_fixture.create_dashboard_application(user=user)

    with override_settings(DEBUG=True):
        enterprise_data_fixture.enable_enterprise()
        service = enterprise_data_fixture.create_service(
            LocalBaserowGroupedAggregateRows,
            integration_args={"application": dashboard},
        )
        data_source = enterprise_data_fixture.create_dashboard_data_source(
            dashboard=dashboard, service=service
        )

    enterprise_data_fixture.delete_all_licenses()

    dispatch_context = DashboardDispatchContext(HttpRequest(), dashboard.workspace)
    with pytest.raises(FeaturesNotAvailableError):
        DashboardDataSourceService().dispatch_data_source(
            user, data_source.id, dispatch_context
        )
