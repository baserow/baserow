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
are added as new cases come up.

## How a user-template copy is made

Creating, updating and installing a template export applications and import them into
another workspace with this `ImportExportConfig`. Download is a normal workspace export
of the template workspace and needs no rule of its own.

| Setting | Value | Effect |
| --- | --- | --- |
| `ImportExportConfig.exclude_sensitive_data` | `True` | Every `sensitive_fields` entry is exported as `None` |
| `ImportExportConfig.include_permission_data` | `False` | Role assignments are not exported |
| `ImportExportConfig.is_user_template` | `True` (to add) | The flag every module keys template-specific rules on |
| `id_mapping["import_workspace_id"]` | the template workspace | People and workspace checks resolve against a memberless workspace |
| `ImportExportConfig.workspace_for_user_references` | unset, or the template workspace | Same, for database user references |

The template workspace has no members, so every reference mapped by email or username
resolves to nobody; many people rules are `done` only because of this. Existing flags
such as `is_duplicate` are ambiguous: key every template-specific rule on
`is_user_template`. Enforce secrets on the export side; several export paths don't
receive the config yet (rows marked "Pass the config through").

## Integration credentials

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Integrations | `IntegrationHandler.import_integration` receives no config; pass it through if an import-side rule needs it | to do | WAB |
| Dashboard | Pass the config through `DashboardApplicationType.export_serialized` to `export_integration` | to do | WAB |
| Integrations | `sensitive_fields` on `SMTPIntegrationType`, `SlackBotIntegrationType`, `AIIntegrationType` (`ai_settings`) | done | WAB |
| Builder, automation | `BuilderApplicationType.export_serialized` and `AutomationApplicationType.export_serialized` pass the config to `IntegrationHandler.export_integration` | done | WAB |
| Database (button field) | `DatabaseApplicationType.export_serialized` passes the config to `IntegrationHandler.export_integration`, which applies `sensitive_fields` | done | core/database |

## Secrets in service settings

Request URLs and link URLs, such as `OpenUrlWorkflowActionType.url`, are handled as in a
workspace export; see #6116.

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Integrations | `CoreResponseServiceType` must mark `headers` sensitive | to do | WAB |
| Builder | Pass the config through `PageHandler.export_page` to data sources, workflow actions and their services; see #6115 | to do | WAB |
| Automation | Pass the config through `AutomationNodeType.serialize_property` to the node service; see #6115 | to do | WAB |
| Dashboard | Pass the config through `DashboardDataSourceHandler.export_data_source` to the data source service | to do | WAB |
| Integrations | `sensitive_fields` declared on `CoreHTTPRequestServiceType` (headers, query parameters, form data, body) and `CoreSMTPEmailServiceType`; applied only where the config reaches the service export, today the button field (builder and automation: rows above) | done | WAB |
| Database (button field) | `DatabaseWorkflowServiceActionType.export_serialized` blanks the service's sensitive values | done | core/database |

## Login provider secrets

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Builder | Pass the config through `UserSourceHandler.export_user_source` to auth providers | to do | WAB |
| Enterprise SSO | `OpenIdConnectAppAuthProviderType` must mark `secret` sensitive | to do | WAB |
| Enterprise SSO | `SamlAppAuthProviderType` must remove `metadata` and reset `is_verified` | to do | WAB |

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
| Integrations | `CoreHTTPTriggerServiceType.import_serialized` must regenerate `uid` on `is_user_template` and on install, not only on `is_duplicate` | to do | WAB |
| Integrations | `CoreInboundEmailTriggerServiceType.import_serialized` regenerates `token` on every import that is not publishing | done | WAB |

## Test run data

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Builder, automation, dashboard | `sample_data` of every service removed, in one place in `baserow.core.services` | to do | WAB |
| Database (button field) | `DatabaseWorkflowServiceActionType.serialize_property` drops `sample_data` | done | core/database |

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
| Integrations | Raw user ids in Local Baserow service filter values (`LocalBaserowTableServiceFilterableMixin.serialize_filters`, `deserialize_filters`) for user and collaborator filters removed | to do | WAB |
| Enterprise | SAML identity provider metadata removed (see Login provider secrets) | to do | WAB |
| Database | Row `created_by` and `last_modified_by` are mapped by email in `DatabaseApplicationType.import_serialized`; memberless target gives nobody | done | core/database |
| Database | Collaborator cells (`MultipleCollaboratorsFieldType.set_import_serialized_value`) and user filters (`UserIsViewFilterType`, `MultipleCollaboratorsHasViewFilterType`) map by email; memberless target gives nobody | done | core/database |
| Database | Form conditions (`FormViewType`) and conditional color filters (`ConditionalColorValueProviderType.set_import_serialized_value`) are exported with raw user ids; the filter import maps by email, so they become empty | done | core/database |
| Database, premium | View owners: `ViewType.import_serialized` maps `owned_by` against members; `PersonalViewOwnershipType.can_import_view` skips personal views | done | core/database |
| Enterprise | `RoleAssignmentSerializationProcessorType` skips role assignments, of users, teams and agents, when `include_permission_data` is `False` | done | core/database |
| Automation | `AutomationWorkflowHandler.export_workflow` exports no `notification_recipient_emails` unless `is_duplicate`; `import_workflow_only` maps them to target workspace users | done | WAB |

## Who services run as

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Core | Template creation and content update must not send `application_imported` with the author, or the template's integrations run as the author | to do | core/database |
| Integrations | An integration running as an agent (#6064): `authorized_subject_type` and `authorized_subject_id` are in `LocalBaserowIntegrationType.sensitive_fields`, so they are removed unless publishing | in #6064 | WAB |
| Integrations | `authorized_user` is in `LocalBaserowIntegrationType.sensitive_fields`, so it is exported as `None` wherever the config is passed; the dashboard path relies on `import_serialized` mapping against `import_workspace_id` members | done | core/database |
| Integrations | `LocalBaserowIntegrationType.after_import` sets the installer when install sends `application_imported` with the installer, as `CoreHandler.install_template` does | done | core/database |
| Enterprise | `LocalBaserowTableDataSyncType.import_serialized` always clears `authorized_user_id` | done | core/database |

## References outside the template

An id that is not in `id_mapping` must become `None` on `is_user_template`. Keeping the
raw id, or `.get(id, id)`, is not allowed.

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Integrations | `LocalBaserowTableServiceType.deserialize_property` keeps an unmapped `table_id` on `is_duplicate` and when no table was copied | to do | WAB |
| Integrations | `LocalBaserowViewServiceType.deserialize_property` keeps `view_id` when no view was copied | to do | WAB |
| Integrations | Filter `field_id` in `LocalBaserowTableServiceFilterableMixin.deserialize_filters` and sort `field_id` in `LocalBaserowTableServiceSortableMixin.deserialize_sorts` | to do | WAB |
| Integrations | `LocalBaserowAggregateRowsUserServiceType.deserialize_property` (`field_id`) | to do | WAB |
| Integrations | `LocalBaserowFieldsUpdatedServiceType.deserialize_property` (`field_ids`) keeps raw ids when no field was copied | to do | WAB |
| Premium | `LocalBaserowGroupedAggregateRowsUserServiceType.create_instance_from_serialized` keeps series, group by and sort field ids when no field was copied | to do | WAB |
| Enterprise | `LocalBaserowUserSourceType.deserialize_property` keeps `table_id` and field ids when no table was copied | to do | WAB |
| Dashboard | `DashboardDataSourceHandler.import_data_source` resolves the integration with `.get(id, id)` | to do | WAB |
| Enterprise | `LocalBaserowTableDataSyncType.import_serialized` must clear an unmapped source table and remap or clear `source_table_view_id` | to do | core/database |
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
| Automation | `AutomationWorkflowHandler.import_workflow_only` sets `state` to draft on import (low priority) | to do | core/database |
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
| Builder | Installed copies keep embedded HTML off until the installer turns it on (per-application untrusted content flag) | to do | WAB |
| Builder | `IFrameElementType` forces `allow_same_origin` off in the template and in installs | to do | WAB |

## Custom code

| Module | What enforces it | Status | Owner |
| --- | --- | --- | --- |
| Enterprise builder | `CustomCodeBuilderApplicationTypeMixin.import_serialized` and `CoreCodeActionType` respect the per-application untrusted content flag, off in installed copies | to do | WAB |
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
