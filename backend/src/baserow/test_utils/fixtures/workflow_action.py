from baserow.contrib.builder.workflow_actions.models import (
    CoreCSVFileReaderWorkflowAction,
    CoreHTTPRequestWorkflowAction,
    LocalBaserowCreateRowsWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    LocalBaserowUpdateRowsWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
    NotificationWorkflowAction,
    OpenPageWorkflowAction,
)


class WorkflowActionFixture:
    def create_notification_workflow_action(self, **kwargs):
        return self.create_workflow_action(NotificationWorkflowAction, **kwargs)

    def create_open_page_workflow_action(self, **kwargs):
        return self.create_workflow_action(OpenPageWorkflowAction, **kwargs)

    def create_builder_workflow_service_action(self, model_class, **kwargs):
        if "service" not in kwargs:
            user = kwargs.pop("user", self.create_user())
            integration = self.create_local_baserow_integration(
                application=kwargs["page"].builder, user=user
            )
            if model_class is LocalBaserowCreateRowsWorkflowAction:
                kwargs["service"] = self.create_local_baserow_create_rows_service(
                    integration=integration,
                )
            elif model_class is LocalBaserowUpdateRowsWorkflowAction:
                kwargs["service"] = self.create_local_baserow_update_rows_service(
                    integration=integration,
                )
            else:
                kwargs["service"] = self.create_local_baserow_upsert_row_service(
                    integration=integration,
                )
        return self.create_workflow_action(model_class, **kwargs)

    def create_core_http_request_workflow_action(self, **kwargs):
        return self.create_builder_workflow_service_action(
            CoreHTTPRequestWorkflowAction, **kwargs
        )

    def create_core_csv_file_reader_workflow_action(self, **kwargs):
        if "service" not in kwargs:
            kwargs["service"] = self.create_core_csv_file_reader_service()
        return self.create_builder_workflow_service_action(
            CoreCSVFileReaderWorkflowAction, **kwargs
        )

    def create_local_baserow_create_row_workflow_action(self, **kwargs):
        return self.create_builder_workflow_service_action(
            LocalBaserowCreateRowWorkflowAction, **kwargs
        )

    def create_local_baserow_create_rows_workflow_action(self, **kwargs):
        if "service" not in kwargs:
            kwargs["service"] = self.create_local_baserow_create_rows_service()
        return self.create_builder_workflow_service_action(
            LocalBaserowCreateRowsWorkflowAction, **kwargs
        )

    def create_local_baserow_update_row_workflow_action(self, **kwargs):
        return self.create_builder_workflow_service_action(
            LocalBaserowUpdateRowWorkflowAction, **kwargs
        )

    def create_local_baserow_update_rows_workflow_action(self, **kwargs):
        if "service" not in kwargs:
            kwargs["service"] = self.create_local_baserow_update_rows_service()
        return self.create_builder_workflow_service_action(
            LocalBaserowUpdateRowsWorkflowAction, **kwargs
        )

    def create_local_baserow_delete_row_workflow_action(self, **kwargs):
        return self.create_builder_workflow_service_action(
            LocalBaserowDeleteRowWorkflowAction, **kwargs
        )

    def create_workflow_action(self, model_class, **kwargs):
        if "order" not in kwargs:
            kwargs["order"] = 0

        if "page" not in kwargs:
            if "element" in kwargs:
                kwargs["page"] = kwargs["element"].page
            else:
                kwargs["page"] = self.create_builder_page(user=kwargs.get("user", None))

        return model_class.objects.create(**kwargs)
