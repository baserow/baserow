from django.db.models.signals import post_delete

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service


def after_permanently_deleted(sender, instance, **kwargs):
    """
    Delete the service related to the node.
    """

    try:
        if instance.service_id:
            service = instance.service
            ServiceHandler().delete_service(service.get_type(), service)
    except Service.DoesNotExist:
        # Although cascade deletion should safely handle related models, it may
        # occasionally raise a DoesNotExist error.
        #
        # If the service does not exist, there is nothing to delete.
        pass


def connect_to_node_pre_delete_signal():
    post_delete.connect(after_permanently_deleted, AutomationNode)
