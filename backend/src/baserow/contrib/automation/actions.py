from django.utils.translation import gettext_lazy as _

AUTOMATION_ACTION_CONTEXT = _(
    'in automation "%(automation_name)s" (%(automation_id)s).'
)

AUTOMATION_WORKFLOW_CONTEXT = _(
    'in workflow (%(workflow_id)s) in automation "%(automation_name)s" (%(automation_id)s).'
)
