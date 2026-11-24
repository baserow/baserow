# User template content rules

This document is the cross-module reference for the content rules of user templates.
[ADR 008 §2](../../decisions/008-template-marketplace.md#2-the-content-is-a-hidden-workspace)
decides what happens to each kind of risky data when a user template is created,
installed and downloaded. This document says how each rule is enforced, per module, and
who owns the code that enforces it.

Status is `done` when the current code already enforces the rule for a user-template
copy made as described below, `in #N` when an open pull request enforces it, and `to do`
otherwise. Owner is the team that owns the code: `core/database`, or `WAB` (builder,
automation, dashboard, integrations). Statuses reflect the code as of October 2026; rows
are added as new cases come up. The WAB fixes tracked in
[issue #6330](https://github.com/baserow/baserow/issues/6330#issuecomment-6295816218)
are reflected below.

## How a user-template copy is made

Creating, updating and installing a template export applications and import them into
another workspace with this `ImportExportConfig`. Download is a normal workspace export
of the template workspace and needs no rule of its own.

| Setting | Value | Effect |
| --- | --- | --- |
| `ImportExportConfig.exclude_sensitive_data` | `True` | Every `sensitive_fields` entry is exported as `None` |
| `ImportExportConfig.include_permission_data` | `False` | Role assignments are not exported |
| `ImportExportConfig.is_user_template` | `True` | The flag every module keys template-specific rules on |
| `id_mapping["import_workspace_id"]` | the template workspace | People and workspace checks resolve against a memberless workspace |
| `ImportExportConfig.workspace_for_user_references` | unset, or the template workspace | Same, for database user references |

The template workspace has no members, so every reference mapped by email or username
resolves to nobody; many people rules are `done` only because of this. Existing flags
such as `is_duplicate` are ambiguous: key every template-specific rule on
`is_user_template`. Enforce secrets on the export side; the Builder, Automation and
Dashboard export paths pass the config through to their integrations and services.

## Integration credentials

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Integrations | `IntegrationHandler.import_integration` accepts `import_export_config` and forwards it to the integration type's `import_serialized` | done | WAB |
| Dashboard | `DashboardApplicationType.export_serialized` passes the config to `IntegrationHandler.export_integration` | done | WAB |
| Integrations | `sensitive_fields` on `SMTPIntegrationType`, `SlackBotIntegrationType`, `AIIntegrationType` (`ai_settings`) | done | WAB |
| Builder, automation | `BuilderApplicationType.export_serialized` and `AutomationApplicationType.export_serialized` pass the config to `IntegrationHandler.export_integration` | done | WAB |
| Database (button field) | `DatabaseApplicationType.export_serialized` passes the config to `IntegrationHandler.export_integration`, which applies `sensitive_fields` | done | core/database |

## Secrets in service settings

Request URLs and link URLs, such as `OpenUrlWorkflowActionType.url`, are handled as in a
workspace export; see #6116.

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Integrations | `CoreResponseServiceType.serialize_property` exports no response headers (names or values) when `exclude_sensitive_data=True`, including user-template copies; internal copies with sensitive-data removal disabled retain them | done | WAB |
| Builder | `PageHandler.export_page` passes the config to data sources, workflow actions and their services; see #6115 | done | WAB |
| Automation | `AutomationNodeType.serialize_property` passes the config to the node service; see #6115 | done | WAB |
| Dashboard | `DashboardDataSourceHandler.export_data_source` passes the config to the data source service | done | WAB |
| Integrations | `sensitive_fields` declared on `CoreHTTPRequestServiceType` (headers, query parameters, form data, body) and `CoreSMTPEmailServiceType`; applied by the shared service export across Builder, Automation, Dashboard and database button fields | done | WAB |
| Database (button field) | `DatabaseWorkflowServiceActionType.serialize_property` delegates to the shared service export, which blanks sensitive values | done | core/database |

## Login provider secrets

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Builder | `UserSourceHandler.export_user_source` passes the config through `UserSourceType.serialize_property` to auth providers | done | WAB |
| Enterprise SSO | `OpenIdConnectAppAuthProviderType.sensitive_fields` removes `secret`; import restores an empty string | done | WAB |
| Enterprise SSO | `SamlAppAuthProviderType.sensitive_fields` removes `metadata` and `is_verified` when `exclude_sensitive_data=True`; import restores empty metadata and an unverified login | done | WAB |

## Data sync connections

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Database | All connection settings removed: `ical_url` on `ICalCalendarDataSyncType`, Postgres host, port, user, database, schema, table and SSL mode, Jira URL, username, project and authentication, GitHub owner and repo, GitLab URL and project | to do | core/database |
| Database | `DataSyncType.export_serialized` must not keep `last_error` | to do | core/database |
| Database | `two_way_sync` (in `BASE_DATA_SYNC_ALLOWED_FIELDS`) forced off | to do | core/database |
| Database | `sensitive_fields` on `PostgreSQLDataSyncType` (password), `JiraIssuesDataSyncType`, `GitHubIssuesDataSyncType`, `GitLabIssuesDataSyncType`, `HubspotContactsDataSyncType` (tokens) | done | core/database |
| Enterprise | `PeriodicDataSyncInterval` is not exported, so scheduled sync is off | done | core/database |
| Database | Last synced rows are exported like any other table rows | done | core/database |
| Enterprise | `LocalBaserowTableDataSyncType.import_serialized` remaps a source table inside the template and its `field_<id>` property keys | done | core/database |

## Trigger addresses

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Integrations | `CoreHTTPTriggerServiceType.import_serialized` regenerates `uid` on every non-publishing import, including user-template creation and installation | done | WAB |
| Integrations | `CoreInboundEmailTriggerServiceType.import_serialized` regenerates `token` on every import that is not publishing | done | WAB |

## Test run data

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Builder, automation, dashboard | `ServiceType.export_serialized` recursively replaces `sample_data` values with placeholders for user templates and exports with `exclude_sensitive_data=True`, preserving keys, JSON types and structure for schema inference. Stored errors are removed. Internal copies with sensitive-data removal disabled retain original samples. Property names are retained and may still contain user-provided information. | done | WAB |
| Database (button field) | Button services use the same shared export rules: sanitized samples for user templates and exports with sensitive-data removal enabled; original samples for internal copies | done | core/database |

## Passwords

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Database | `PasswordFieldType` cells exported or imported as empty. This also removes builder app user passwords, which live in password fields | to do | core/database |
| Database | A password field keeps no default value in a template (view default row values, `ViewType._export_default_row_values`) | to do | core/database |

## People of the source workspace

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Database | Rich text mentions in `LongTextFieldType` become a neutral `@user` | to do | core/database |
| Premium | `AIFieldType.import_serialized` drops `ai_auto_update_user_id` only when not `is_duplicate`; must key on `is_user_template` | to do | core/database |
| Integrations | `LocalBaserowTableServiceFilterableMixin.serialize_filters` clears user and collaborator filter values when `exclude_sensitive_data=True`, except a direct `get("provider.path")` reference. Raw values, constants and composed formulas are cleared; exports with sensitive-data removal disabled retain their values. | done | WAB |
| Enterprise | `SamlAppAuthProviderType.sensitive_fields` removes SAML identity provider metadata when `exclude_sensitive_data=True` (see Login provider secrets) | done | WAB |
| Database | Row `created_by` and `last_modified_by` are mapped by email in `DatabaseApplicationType.import_serialized`; memberless target gives nobody | done | core/database |
| Database | Collaborator cells (`MultipleCollaboratorsFieldType.set_import_serialized_value`) and user filters (`UserIsViewFilterType`, `MultipleCollaboratorsHasViewFilterType`) map by email; memberless target gives nobody | done | core/database |
| Database | Form conditions (`FormViewType`) and conditional color filters (`ConditionalColorValueProviderType.set_import_serialized_value`) are exported with raw user ids; the filter import maps by email, so they become empty | done | core/database |
| Database, premium | View owners: `ViewType.import_serialized` maps `owned_by` against members; `PersonalViewOwnershipType.can_import_view` skips personal views | done | core/database |
| Enterprise | `RoleAssignmentSerializationProcessorType` skips role assignments, of users, teams and identities, when `include_permission_data` is `False` | done | core/database |
| Automation | `AutomationWorkflowHandler.export_workflow` exports no `notification_recipient_emails` unless `is_duplicate`; `import_workflow_only` maps them to target workspace users | done | WAB |

## Who services run as

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Core | Template content is imported without sending `application_imported` with the author; installation calls `CoreHandler.mark_applications_installed_from_template` with the installer | done | core/database |
| Integrations | `authorized_subject_type` and `authorized_subject_id` are in `LocalBaserowIntegrationType.sensitive_fields`; sensitive exports remove them, while publishing explicitly preserves them (#6064) | done | WAB |
| Integrations | `LocalBaserowIntegrationType.after_import` authorizes the installer when `CoreHandler.mark_applications_installed_from_template` sends `application_imported`; this applies to official and user-template installation | done | core/database |
| Enterprise | `LocalBaserowTableDataSyncType.import_serialized` always clears `authorized_user_id` | done | core/database |

## References outside the template

External application imports seed empty table, view and field mappings, even when no
database is included. References absent from these mappings are cleared or their
dependent settings are dropped. Internal copies keep their existing reference behavior.

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Integrations | `LocalBaserowTableServiceType.deserialize_property` clears unmapped `table_id` on external imports; internal duplicates can keep unmapped references | done | WAB |
| Integrations | `LocalBaserowViewServiceType.deserialize_property` clears unmapped `view_id` when importing with seeded mappings | done | WAB |
| Integrations | `import_refinement_field_id` remaps filter and sort fields; `deserialize_filters` and `deserialize_sorts` drop conditions and sorts whose fields were not imported | done | WAB |
| Integrations | `LocalBaserowAggregateRowsUserServiceType.deserialize_property` clears unmapped aggregate `field_id` using `import_refinement_field_id` | done | WAB |
| Integrations | `LocalBaserowFieldsUpdatedTriggerServiceType.deserialize_property` remaps watched `field_ids` and drops fields absent from the import | done | WAB |
| Integrations | `LocalBaserowUpsertRowServiceType` remaps field mappings and skips mappings whose fields were not imported | done | WAB |
| Premium | `LocalBaserowGroupedAggregateRowsUserServiceType.create_instance_from_serialized` clears unmapped series and group-by fields and drops unmapped sort references | done | WAB |
| Enterprise | `LocalBaserowUserSourceType.deserialize_property` clears unmapped table, email, name and role field ids; the Local Baserow password provider clears its unmapped password field | done | WAB |
| Enterprise | The Local Baserow search service remaps or drops search and included field ids and restricts imported field relations to the imported table | done | WAB |
| Dashboard | `DashboardDataSourceHandler.import_data_source` uses `IntegrationHandler.get_integration_for_import` with `keep_unmapped=False`, clearing unmapped integrations | done | WAB |
| Enterprise | `LocalBaserowTableDataSyncType.import_serialized` imports no data sync, leaving a plain editable table, when the source table or the `source_table_view_id` view was not copied; a database duplicate keeps them, staying synced to the original | done | core/database |
| Integrations | `CoreStartWorkflowServiceType.import_workflow_id` refuses a workflow outside `import_workspace_id` | done | WAB |

Button field row actions use the Local Baserow service types above and follow them.

## Shared views and forms

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Database | `ViewType.export_serialized` exports `public`; it must be `False` in the template and installed copies, as `ViewHandler.duplicate_view` does | to do | core/database |
| Database | View slug and view password are not exported | done | core/database |

## Running services

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Automation | `AutomationWorkflowHandler.import_workflow_only` forces `state` to draft for external imports, including user templates; internal copies and official template imports retain their serialized state | done | core/database |
| Database | Two-way and scheduled data sync off (see Data sync connections) | to do | core/database |
| Automation | Only draft workflows are exported; published workflows are not part of the workspace | done | WAB |
| Automation | Test run fields (`allow_test_run_until`) are not exported by `AutomationWorkflowHandler.export_workflow` | done | WAB |

## Files

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Core | A template-owned copy of every file, with `UserFile.unique` starting with `tpl` and the zero-padded template workspace id | to do | core/database |
| Core | `UserFileHandler.generate_unique` never returns a unique starting with `tpl` | to do | core/database |
| Core | Upload deduplication in `UserFileHandler.upload_user_file` skips template files | to do | core/database |
| Core | Install creates normally named files | to do | core/database |
| Core | Template files are deleted with the template | to do | core/database |

## Active content

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Builder frontend | Template preview always sandboxes IFrame embeds, including Repeat items (`sandboxPermissions` in `IFrameElement.vue`) | to do | core/database |
| Builder | `IFrameElementType` records imported iframe elements in the import report; `IFrameElement.vue` blocks them while the application has `untrusted_content`, until the installer reviews and trusts it | done | WAB |
| Builder | `allow_same_origin` is preserved; imported iframe content requires application-level review instead of forcing this setting off | done | WAB |

## Custom code

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Enterprise builder | `CustomCodeBuilderApplicationTypeMixin.import_serialized` records custom code and external scripts in the import report; `PublicCustomCodeView` and `CoreCodeActionType.dispatch` block custom code while the application has `untrusted_content` | done | WAB |
| Builder frontend | The template allowlist has no `ReadApplicationOperationType`, so the builder preview and `PublicCustomCodeView` refuse template viewers; custom code is only added by `PublicPageContent.vue` | done | WAB |
| Builder | `DispatchBuilderWorkflowActionOperationType` is not on the template allowlist, so `CoreCodeActionType` never runs in the preview | done | WAB |

## Cell values and other content

Kept as is. Nothing enforces it; the author is told before creating or updating content
that everything not removed is shared as it is.

## Preview

ADR 008 §3: the preview is read-only and inert. Official template previews are
unchanged. The rules below apply to user templates only.

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Core | Access is decided by the template state and the actor (ADR §4), not by `Workspace.has_template()` in `AllowIfTemplatePermissionManagerType` and its module subclasses | to do | core/database |
| Core | No `LoginUserSourceOperationType` on user templates | to do | core/database |
| Builder | No `DispatchDataSourceOperationType` on user templates | to do | core/database |
| Dashboard | No `DispatchDashboardDataSourceOperationType` on user templates | to do | core/database |
| Builder frontend | IFrame embeds sandboxed (see Active content) | to do | core/database |
| All | The template allowlists hold list, read and dispatch operations plus `LoginUserSourceOperationType` (removed above), so viewers cannot write | done | core/database |
