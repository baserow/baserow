from django.db import transaction
from django.urls import reverse

import pytest

from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.core.exceptions import UntrustedContentCannotBePublished
from baserow.core.models import Job


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["builder", "automation"])
def test_untrusted_content_cannot_start_publish_job(api_client, data_fixture, kind):
    """Reject untrusted publication before any background job is queued."""

    user, token = data_fixture.create_user_and_token()
    if kind == "builder":
        builder = data_fixture.create_builder_application(
            user=user, untrusted_content=True
        )
        domain = data_fixture.create_builder_custom_domain(builder=builder)
        url = reverse("api:builder:domains:publish", kwargs={"domain_id": domain.id})
    else:
        automation = data_fixture.create_automation_application(user=user)
        workflow = data_fixture.create_automation_workflow(
            automation=automation, untrusted_content=True
        )
        url = reverse(
            "api:automation:workflows:async_publish",
            kwargs={"workflow_id": workflow.id},
        )
    before = Job.objects.count()
    response = api_client.post(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_UNTRUSTED_CONTENT_CANNOT_BE_PUBLISHED"
    assert Job.objects.count() == before


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["builder", "automation"])
def test_publish_rechecks_persisted_trust_before_replacing_publication(
    data_fixture, kind
):
    """Reload trust at execution time and preserve the previous live version."""

    if kind == "builder":
        owner = data_fixture.create_builder_application()
        target = data_fixture.create_builder_custom_domain(builder=owner)
        handler = DomainHandler()
    else:
        owner = data_fixture.create_automation_workflow()
        target = owner
        handler = AutomationWorkflowHandler()
    with transaction.atomic():
        previous = handler.publish(target)
    if kind == "builder":
        target.refresh_from_db()
        previous_id = target.published_to_id
    else:
        previous_id = previous.id
    owner.__class__.objects.filter(pk=owner.pk).update(untrusted_content=True)
    with transaction.atomic(), pytest.raises(UntrustedContentCannotBePublished):
        handler.publish(target)
    owner.refresh_from_db()
    assert owner.untrusted_content is True
    if kind == "builder":
        target.refresh_from_db()
        assert target.published_to_id == previous_id
    else:
        assert handler.get_published_workflow(owner).id == previous_id
