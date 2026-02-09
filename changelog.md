# Changelog

## Released 2.0.6

### New features
* [Core] Added more advanced formulas. [#4318](https://github.com/baserow/baserow/-/issues/4318)
* [Core] Allow array properties to be selected in the formula context when expert mode is selected. [#4485](https://github.com/baserow/baserow/-/issues/4485)

### Bug fixes
* [Builder] Resolve an issue with styling button fields in table elements. [#4494](https://github.com/baserow/baserow/-/issues/4494)
* [Database] Ensure m2m field indexes are all set.
* [Database] Prevent creating a new constraint when the enter key of the default value is pressed.


## Released 2.0.5

### Bug fixes
* [Builder] Resolved a bug which prevented user sources from being created or updated with a user source table.


## Released 2.0.4

### New features
* [Core] Allow setting multiple BASEROW_PUBLIC_URL #2593 [#2593](https://github.com/baserow/baserow/-/issues/2593)
* [Database] Allow to add missing fields to date dependency configuration [#4228](https://gitlab.com/baserow/baserow/-/issues/4228)
* [Builder] Added a 'Create new data source' link at the bottom of iterate/table element dropdowns for quicker data source creation.
* [Integration] Improved the Local Baserow action fields so that they inform users about what data type they expect to receive.

### Bug fixes
* [Database] handle date overflow in postgresql -> python conversion [#3324](https://gitlab.com/baserow/baserow/-/issues/3324)
* [Database] Timeline view - fetch all rows again if a filter is disabled. [#4136](https://github.com/baserow/baserow/-/issues/4136)
* [Builder] Show a specific error when a page is being renamed to an existing page's name. [#4183](https://github.com/baserow/baserow/-/issues/4183)
* [Automation] Show a specific error when a workflow is being renamed to an existing workflow's name. [#4183](https://github.com/baserow/baserow/-/issues/4183)
* [Automation] Fixed a potential crash while deleting a workflow. [#4293](https://github.com/baserow/baserow/-/issues/4293)
* [Database] Handle exceptions like GenerativeAIPromptError in UI [#4350](https://github.com/baserow/baserow/-/issues/4350)
* [Core] Resolved a bug which prevented formula fields from working correctly with HTML content. [#4377](https://github.com/baserow/baserow/-/issues/4377)
* [Builder] Gracefully handle fetching data source services when the specific instance is missing. [#4389](https://github.com/baserow/baserow/-/issues/4389)
* [Builder] Fixed a bug where domain names were not correctly validated during domain creation. [#4399](https://github.com/baserow/baserow/-/issues/4399)
* [Core] Improved error handling when FormulaField value is not JSON serializable. [#4402](https://github.com/baserow/baserow/-/issues/4402)
* [Database] Do not fail hard when ArrayValueSerializer throws ConversionSyntax exception [#4424](https://github.com/baserow/baserow/-/issues/4424)
* [Database] Fix an issue where "Rows enter view" webhook shows stale rows when webhook is deleted and recreated [#4437](https://github.com/baserow/baserow/-/issues/4437)
* [Builder] Resolved a bug in element visibility which prevented form data from being used.
* [Builder] Resolved a bug which prevented the table element fields from being styled.

### Refactors
* [Database] Optimize test suite by deferring heavy signals by default [#4373](https://github.com/baserow/baserow/-/issues/4373)
* [Integration] Improved one-way and two-way data sync support in Local Baserow actions.


## Released 2.0.3

### New features
* [Core] Allow changing account email address. [#1420](https://github.com/baserow/baserow/-/issues/1420)
* [Database] Paste values from a single row into many rows [#3194](https://gitlab.com/baserow/baserow/-/issues/3194)
* [Database] Run AI field generation in parallel [#4227](https://github.com/baserow/baserow/-/issues/4227)
* [Database] Show jobs for AI Field in modal [#4264](https://github.com/baserow/baserow/-/issues/4264)
* [Core] Synchronizes the dev docs with the assistant knowledge base documents.

### Bug fixes
* [Database] Fix OpenAPI spec for generate_table_ai_field_value [#4339](https://github.com/baserow/baserow/-/issues/4339)
* [Core] Change WebSocket connection closed error message.
* [Core] Fix backup_baserow management command by using correct pg3 dbname. [#4308](https://github.com/baserow/baserow/-/issues/4308)
* [Builder] Fix bug in the Helm chart where the AI-assistant LLM model was always set.
* [Database] Improve performance in the `database_pendingsearchvalueupdate` table with many entries.

### Refactors
* [Database] Improved storage usage performance.
* [Builder] Refactored the element theme override form so that it works better on smaller screens.
* [Core] Update email compiler dependencies
* [Core] Update frontend dependencies 2025-12-03


## Released 2.0.2

### New features
* [Integration] Allow the Local Baserow 'update row' service to update data synced tables with writable fields. [#3799](https://github.com/baserow/baserow/-/issues/3799)

### Bug fixes
* [Database] Adjust image orientation based on exif data [#4247](https://github.com/baserow/baserow/-/issues/4247)
* [Automation] Fixed a bug where creating a workflow would cause a crash for another user viewing a different app. [#4293](https://github.com/baserow/baserow/-/issues/4293)
* [Automation] Allow to duplicate nodes inside container nodes [#4294](https://github.com/baserow/baserow/-/issues/4294)
* [Builder] Improve performances when editing a create/update workflow action with a lot of table fields
* [Integration] Resolved BASEROW_INTEGRATIONS_PERIODIC_MINUTE_MIN env variable bug.

### Refactors
* [Database] Make read/write DB routing consistent for http requests and background tasks [#3848](https://gitlab.com/baserow/baserow/-/issues/3848)
* [Builder] Fix missing form data after first render (SSR) [#4268](https://github.com/baserow/baserow/-/issues/4268)
* [Core] Improve formula editor

### Breaking API changes
* [Builder] Number field values returned by local baserow integrations are now actual numbers instead of string [#4219](https://github.com/baserow/baserow/-/issues/4219)


## Released 2.0.1

### Bug fixes
* [Core] Don't show the Assistant panel if the LLM_MODEL env variable is not configured [#4280](https://github.com/baserow/baserow/-/issues/4280)
* [Builder] Fix visibility condition not working if data property wasn't used in page
* [Automation] Save data preparation for table that don't have trigger associated to it


## Released 2.0.0

### New features
* [Builder] Element can be visually hidden on complex conditions [#2566](https://gitlab.com/baserow/baserow/-/issues/2566)
* [Database]  Regenerate all table/view AI field values at once  [#2586](https://gitlab.com/baserow/baserow/-/issues/2586)
* [Builder] Support advanced formulas. Formulas can now use functions and operators. [#3258](https://github.com/baserow/baserow/-/issues/3258)
* [Database] Multiple collaborators lookup fields filters [#3450](https://gitlab.com/baserow/baserow/-/issues/3450)
* [Database] Duration lookup field type filters [#3471](https://gitlab.com/baserow/baserow/-/issues/3471)
* [Database] Ability to find items anywhere in the workspace [#3732](https://gitlab.com/baserow/baserow/-/issues/3732)
* [Database] Add filters support for AI field [#3801](https://gitlab.com/baserow/baserow/-/issues/3801)
* [Database] Workspace search [#3826](https://github.com/baserow/baserow/-/issues/3826)
* [Database] Date dependencies in table [#3829](https://github.com/baserow/baserow/-/issues/3829)
* [Database] AI field auto-update [#4115](https://gitlab.com/baserow/baserow/-/issues/4115)
* [Builder] Added the AI agent workflow action. [#4116](https://github.com/baserow/baserow/-/issues/4116)
* [Database] Show primary field value in workspace search result for RowSearchType [#4181](https://gitlab.com/baserow/baserow/-/issues/4181)
* [Builder] Introduced the new 'Slack send message' workflow action. [#4237](https://github.com/baserow/baserow/-/issues/4237)
* [Core] Add TOTP 2fa support [#725](https://gitlab.com/baserow/baserow/-/issues/725)
* [Core] Added GitHub actions feature branch pipeline.
* [Core] Introduced Kuma, an AI-powered assistant to help you manage your workspace. [#3676](https://github.com/baserow/baserow/-/issues/3676)
* [Core] Introduced the ability to sync the knowledge base based on an exportable file.
* [Automation] Introducing automation builder; automate repetitive tasks and workflows.
* [Database] Show workspace settings modal if clicked on deactivated AI field.

### Bug fixes
* [Core] Only close the last opened modal when the esc key is pressed. [#3495](https://gitlab.com/baserow/baserow/-/issues/3495)
* [Database] Hide tooltip when value dynamically changes to null [#3501](https://gitlab.com/baserow/baserow/-/issues/3501)
* [Database] Log files that cannot be downloaaded during import [#3581](https://gitlab.com/baserow/baserow/-/issues/3581)
* [Core] Close the dropdown when using the tab key to move out from the collaborators field [#3717](https://gitlab.com/baserow/baserow/-/issues/3717)
* [Database] Long text boxes in forms don't maintain their expanded size. [#3801](https://gitlab.com/baserow/baserow/-/issues/3801)
* [Database] Serialize create/update rows actions execution to keep store consistent [#3850](https://gitlab.com/baserow/baserow/-/issues/3850)
* [Database] Allow formula field to reference AI field with choice output type [#3851](https://gitlab.com/baserow/baserow/-/issues/3851)
* [Database] Allow create new entry in linked table using pop-up window [#4104](https://gitlab.com/baserow/baserow/-/issues/4104)
* [Database] Fix CSV import throwing 'no fetchall attribute' error and respect primary field order [#4163](https://gitlab.com/baserow/baserow/-/issues/4163)
* [Builder] Fix scope issue with form input and repeat elements [#4185](https://gitlab.com/baserow/baserow/-/issues/4185)
* [Builder] Fix formula recursion error when the same data source is used twice in one formula of workflow action [#4195](https://gitlab.com/baserow/baserow/-/issues/4195)
* [Builder] Fix synchronised button loading state in tables [#4268](https://github.com/baserow/baserow/-/issues/4268)
* [Builder] Fix broken menu element
* [Builder] Fix collection element broken when they are in container
* [Database] Fix bug where the form validation does not work if iOS recognizes a phone number in the field name.
* [Builder] Fix workflow action configuration broken
* [Database] Added a tooltip to indicate that indexing is not available for this field type. [#3810](https://gitlab.com/baserow/baserow/-/issues/3810)
* [Core] Allow setting custom base URL for OpenAI. [#4108](https://github.com/baserow/baserow/-/issues/4108)

### Refactors
* [Builder] Added support for Advanced Formulas. [#3258](https://github.com/baserow/baserow/-/issues/3258)

### Breaking API changes
* [Builder] Data source now return content with human property names instead of technical ones [#4135](https://gitlab.com/baserow/baserow/-/issues/4135)


## Released 1.35.3

### New features
* [Database] Allow viewers and higher to export table.

### Bug fixes
* [Database] Fix copy/paste on Safari 18.6+ [#3830](https://gitlab.com/baserow/baserow/-/issues/3830)
* [Database] Removed duplicated spin animation causing loading icon to look slower than intended.

### Refactors
* [Core] Add debug logging to SAML/OAuth2 views to get more information on issues.


## Released 1.35.2

### New features
* [Database] Date dependency - allow to connect two dates as start date/end date, and a duration field, and recalculate other fields if one is modified. [#3735](https://gitlab.com/baserow/baserow/-/issues/3735)

### Bug fixes
* [Builder] Fix timezone issue with date time picker [#3566](https://gitlab.com/baserow/baserow/-/issues/3566)
* [Core] Fix a bug in the Guided Tour that caused a Vue warning. [#3721](https://gitlab.com/baserow/baserow/-/issues/3721)
* [Database] Do not fire for past entries on new webhook [#3811](https://gitlab.com/baserow/baserow/-/issues/3811)
* [Database] Fix filter group api documentation [#3829](https://gitlab.com/baserow/baserow/-/issues/3829)
* [Database] Fix the error when submitting form with collaborator field notification enabled in public forms. [#3834](https://gitlab.com/baserow/baserow/-/issues/3834)
* [Builder] Fixed bug that causes the frontend to crash when an Integration is deleted. [#3835](https://gitlab.com/baserow/baserow/-/issues/3835)
* [Database] Remove comment operations from Ctrl+Z undo stack to prevent accidental deletions [#3837](https://gitlab.com/baserow/baserow/-/issues/3837)
* [Database] Fix a bug with frontend view filters when the root group doesn't have filters. [#3839](https://gitlab.com/baserow/baserow/-/issues/3839)
* [Database] Fix button loading animation of publicly shared view login page.
* [Database] Fix PostgreSQL update with multiple primary keys.
* [Core] Improve SSR performance by only extending the translations once.
* [Database] Prevent multiple concurrent `update_search_data` tasks from being scheduled.
* [Core] Prevent the sync templates task from being scheduled multiple times concurrently.
* [Builder] Reload data source information on authentication
* [Builder] Resolved a bug which prevented formula fields from being filtered upon by external users.
* [Builder] Resolved a table and repeat element bug which inadvertently displayed an error popup.

### Refactors
* [Core] Update backend and frontend dependencies 2025-09-29


## Released 1.35.1

### New features
* [Builder] Allow to set CSS classes for any element [#3752](https://gitlab.com/baserow/baserow/-/issues/3752)

### Bug fixes
* [Database] Added missing translations for ImportFileModal.vue [#3802](https://gitlab.com/baserow/baserow/-/issues/3802)
* [Database] Clears the pendingsearchvalueupdate entries of a table where the workspace table does not exist anymore.
* [Database] Fix a performance regression when deleting rows.
* [Database] Fix performance bug selecting from pendingsearchvalueupdate table.
* [Builder] Resolved a table element bug which allowed users to mark non-filterable fields as filterable to external users.


## Released 1.35.0

### New features
* [Database] Show an asterisk (*) to indicate required fields in forms [#2704](https://gitlab.com/baserow/baserow/-/issues/2704)
* [Dashboard] Add pie and doughnut charts [#3552](https://gitlab.com/baserow/baserow/-/issues/3552)
* [Database] Allow application selection during workspace export [#3734](https://gitlab.com/baserow/baserow/-/issues/3734)
* [Builder] Add environment variable to allow sending request to internal IPs with HTTP request action [#](https://gitlab.com/baserow/baserow/-/issues/)
* [Core] Show highest role on admin user listing page. [#3754](https://gitlab.com/baserow/baserow/-/issues/3754)
* [Database] Two-way PostgreSQL data sync. [#3082](https://gitlab.com/baserow/baserow/-/issues/3082)

### Bug fixes
* [Database] Deactivate data sync and notify user when no proper license is available [#3562](https://gitlab.com/baserow/baserow/-/issues/3562)
* [Database] Skipped fields during CSV import will not overwrite table data [#3652](https://gitlab.com/baserow/baserow/-/issues/3652)
* [Builder] Properly handle error in HTTP request action [#3749](https://gitlab.com/baserow/baserow/-/issues/3749)
* [Builder] Don't show an error message for unused data source [#3760](https://gitlab.com/baserow/baserow/-/issues/3760)
* [Database] Fix undo for single select with default value [#3762](https://gitlab.com/baserow/baserow/-/issues/3762)
* [Builder] Resolved an issue which prevented application builder data sources from being able to read from data-synced tables. [#3763](https://gitlab.com/baserow/baserow/-/issues/3763)
* [Builder] Fix stuck in loading state after field configuration is fixed [#3765](https://gitlab.com/baserow/baserow/-/issues/3765)
* [Database] Fix form single select and multiple select default values when options are restricted [#3769](https://gitlab.com/baserow/baserow/-/issues/3769)
* [Database] Fix count formula for link row fields with null values [#3770](https://gitlab.com/baserow/baserow/-/issues/3770)
* [Database] Fix formula field dependency ordering on row deletion [#3772](https://gitlab.com/baserow/baserow/-/issues/3772)
* [Builder] Allow ISO string as value for date fields [#3776](https://gitlab.com/baserow/baserow/-/issues/3776)
* [Database] Fix empty filters that break real-time filtering with OR condition [#3791](https://gitlab.com/baserow/baserow/-/issues/3791)
* [Database] Fix for skipped_fields being None [#3796](https://gitlab.com/baserow/baserow/-/issues/3796)
* [Database] Do not pass SelectOptionDoesNotBelongToField to sentry [#3797](https://gitlab.com/baserow/baserow/-/issues/3797)
* [Database] Fix duplicated results from OR filters [#3799](https://gitlab.com/baserow/baserow/-/issues/3799)
* [Database] Handle NaN in export_value for NumberField [#3800](https://gitlab.com/baserow/baserow/-/issues/3800)
* [Database] Fix adhoc row coloring and permissions bug.
* [Database] Fix broken export/import with broken via dependency
* [Builder] Fix crash when toggling the share status of a used data source
* [Builder] Fix error while duplicating an application referencing a default role for a deleted data source

### Refactors
* [Core] Fix grammar in workspace invitation related emails. [#3775](https://gitlab.com/baserow/baserow/-/issues/3775)
* [Core] All lock_expiry to add singleton celery tasks.


## Released 1.34.5

### Bug fixes
* [Database] Speed up a slow query to update search vectors and automatically remove stale entries from the pending updates table.

### Refactors
* [Builder] Improve performances of page data sources dispatch endpoint
* [Core] Process storage usage update more often


## Released 1.34.4

### Bug fixes
* [Database] Fix Field `id` expected by got dict error


## Released 1.34.3

### New features
* [Dashboard] Separate bar and line charts as new chart options [#3663](https://gitlab.com/baserow/baserow/-/issues/3663)

### Bug fixes
* [Database] Handle empty number_decimal_places value for number formula field [#3616](https://gitlab.com/baserow/baserow/-/issues/3616)
* [Builder] Remove toast in the editor as it is confusing [#3750](https://gitlab.com/baserow/baserow/-/issues/3750)
* [Database] Do not re-raise mapped exceptions when running jobs [#3753](https://gitlab.com/baserow/baserow/-/issues/3753)
* [Builder] Fix font family from theme not applied to previewed/published page
* [Core] Fixed issue where applications failed to load properly with multiple workspaces
* [Builder] Resolved an issue which prevented data sources from being able to choose a specific view.
* [Database] Stop scheduling search tasks if the workspace is None (i.e. snapshots)

### Refactors
* [Builder] Automatically delete services when workflow actions are deleted
* [Core] Remove obsolete compose versions


## Released 1.34.2

### Bug fixes
* [Builder] Resolved an issue which prevented the table element's button events from working correctly.


## Released 1.34.1

### Bug fixes
* [Builder] Fix error when a shared data source dispatch fails
* [Core] Fix font lighter default css bug.
* [Database] Fix minor issues after the TSVectors refactor.


## Released 1.34.0

### New features
* [Database] Limit the number of linked items returned by default in views. [#161](https://gitlab.com/baserow/baserow/-/issues/161)
* [Database] Add ability to select multiple rows via checkbox or keyboard shortcut for bulk actions [#1923](https://gitlab.com/baserow/baserow/-/issues/1923)
* [Builder] Allow to add custom CSS/JS and external scripts to a published application [#2344](https://gitlab.com/baserow/baserow/-/issues/2344)
* [Database] Optionally auto sync newly added properties to the data sync. [#3423](https://gitlab.com/baserow/baserow/-/issues/3423)
* [Dashboard] Group aggregated values into 'Other' bucket when the number of buckets is not sufficient [#3549](https://gitlab.com/baserow/baserow/-/issues/3549)
* [Builder] Error messages are displayed in the editor when an element, an action or a data source is misconfigured [#3550](https://gitlab.com/baserow/baserow/-/issues/3550)
* [Builder] Improve error message for data source and action errors [#3550](https://gitlab.com/baserow/baserow/-/issues/3550)
* [Builder] Allow sending emails with SMTP [#3551](https://gitlab.com/baserow/baserow/-/issues/3551)
* [Builder] User can define the default count of records returned by the Local Baserow List Rows data source. [#3673](https://gitlab.com/baserow/baserow/-/issues/3673)
* [Builder] Allow to reference previous data source content from a following data source [#3711](https://gitlab.com/baserow/baserow/-/issues/3711)
* [Database] Add support for 'unique with empty' constraint [#647](https://gitlab.com/baserow/baserow/-/issues/647)
* [Core] Allow configuring PostgreSQL read-only replicas.
* [Builder] Add application builder guided tour.
* [Database] Password field API endpoint authentication. [#2321](https://gitlab.com/baserow/baserow/-/issues/2321)
* [Core] Remember instance ID when navigating to pricing page.

### Bug fixes
* [Builder] Fix broken user source authentication for duplicated applications [#3391](https://gitlab.com/baserow/baserow/-/issues/3391)
* [Database] Fix for Collaborator dropdown avatars overlap with created by/modified fields in row editor [#3607](https://gitlab.com/baserow/baserow/-/issues/3607)
* [Database] Fix self reference table look bug. [#3620](https://gitlab.com/baserow/baserow/-/issues/3620)
* [Database] Allow scrolling in field description tooltip. [#3648](https://gitlab.com/baserow/baserow/-/issues/3648)
* [Database] Fix for copy to clipboard fails if document does not have focus on Chrome [#3660](https://gitlab.com/baserow/baserow/-/issues/3660)
* [Database] Fix bug where clearing the cell with `DEL` breaks the file field component [#3671](https://gitlab.com/baserow/baserow/-/issues/3671)
* [Database] Fix a bug while showing form views in templates [#3674](https://gitlab.com/baserow/baserow/-/issues/3674)
* [Database] Prevent form submit when file is renamed [#3681](https://gitlab.com/baserow/baserow/-/issues/3681)
* [Database] Prevent removing brackets in formula when a field is renamed. [#3693](https://gitlab.com/baserow/baserow/-/issues/3693)
* [Database] Fixed issue with special characters being incorrectly rendered in distribution aggregation. [#3695](https://gitlab.com/baserow/baserow/-/issues/3695)
* [Builder] Fix missing licences in published websites [#3725](https://gitlab.com/baserow/baserow/-/issues/3725)
* [Database] Handle DoesNotExist exception in websocket background tasks [#3729](https://gitlab.com/baserow/baserow/-/issues/3729)
* [Database] Additional fixes to number formatting when comma is used as decimal separator.
* [Builder] Context data formula for list row data source were broken on published version
* [Database] Fix Airtable import filter bugs.
* [Builder] Fix crash when a previous action isn't configured
* [Builder] Fix crashing builder when a choice element value formula is referencing a missing data
* [Database] Fix bug where the MCP server didn't accept the single and multiple select ids correctly.
* [Core] Fix BASEROW_OSS_ONLY environment variable.
* [Database] Fix Rich Text Editor floating menus
* [Database] Fix rich text field cell selected border styling bug.

### Refactors
* [Database] Improved search data management - use workspace-wide search table to store tsvectors instead of per-column storage [#3548](https://gitlab.com/baserow/baserow/-/issues/3548)
* [Database] Reduce number of MCP tools by using single tool for rows list and delete.
* [Database] Add the ability to return row_ids from UPDATE statements.
* [Core] Use fakredis as default cache backend for tests


## Released 1.33.4

### New features
* [Builder] Add the HTTP request action to request endpoint [#3234](https://gitlab.com/baserow/baserow/-/issues/3234)
* [Dashboard] Add ability to choose between bar and line series [#3514](https://gitlab.com/baserow/baserow/-/issues/3514)
* [Dashboard] Jira data sync personal access token authentication. [#3558](https://gitlab.com/baserow/baserow/-/issues/3558)

### Bug fixes
* [Database] Fix rating filter style reactivity [#3523](https://gitlab.com/baserow/baserow/-/issues/3523)
* [Builder] Login action are now executed even if the user is already authenticated [#3630](https://gitlab.com/baserow/baserow/-/issues/3630)
* [Builder] Ensure that in the Theme settings, the Table styles are rendered in the preview panel. [#3631](https://gitlab.com/baserow/baserow/-/issues/3631)
* [Builder] Fix styling issues when using Text element with markdown format. [#3632](https://gitlab.com/baserow/baserow/-/issues/3632)
* [Builder] Fix code blocks in markdown code for text element [#3634](https://gitlab.com/baserow/baserow/-/issues/3634)
* [Database] Fixed bug where formula values reset when moving rows. [#3640](https://gitlab.com/baserow/baserow/-/issues/3640)
* [Database] Fix bug where empty numeric fields were displayed as `NaN` in the row edit modal and in forms [#3651](https://gitlab.com/baserow/baserow/-/issues/3651)
* [Builder] Data input type was lost between two reload

### Refactors
* [Database] Send row history broadcast per table, not per row [#3646](https://gitlab.com/baserow/baserow/-/issues/3646)
* [Core] Add pytest-testmon to only run tests affected by changes.
* [Core] Automatically fill the premium seats when registering the license.
* [Database] Introduced `calculate_storage_usage_workspace` hook and `before_rows_create` signal.
* [Core] Minor guided tour changes for reversed trial.
* [Database] Rename 'has' to 'has any of' 
* [Builder] Retry workflow actions on deadlocks
* [Core] Updated backend dependencies to fix dependency security vulnerabilities.
* [Core] Updated frontend dependencies to fix dependency security vulnerabilities.


## Released 1.33.3

### New features
* [Database] Introduce list all tables endpoints via token auth. [#1100](https://gitlab.com/baserow/baserow/-/issues/1100)
* [Database] Be able to specify a default value on multiple select field [#2173](https://gitlab.com/baserow/baserow/-/issues/2173)
* [Database] Support default values for single select field [#2173](https://gitlab.com/baserow/baserow/-/issues/2173)
* [Database] Make AI field editable [#3557](https://gitlab.com/baserow/baserow/-/issues/3557)

### Bug fixes
* [Builder] Fix issue when two columns of a table element have the same value [#3144](https://gitlab.com/baserow/baserow/-/issues/3144)
* [Builder] Allow blank link row values in create and update row actions. [#3524](https://gitlab.com/baserow/baserow/-/issues/3524)
* [Builder] Fix form values being reset before all actions are done [#3530](https://gitlab.com/baserow/baserow/-/issues/3530)
* [Builder] Fix data input not reset after form submition with "Reset after submission" option [#3583](https://gitlab.com/baserow/baserow/-/issues/3583)
* [Builder] Fix choice element missing default value for single select [#3602](https://gitlab.com/baserow/baserow/-/issues/3602)
* [Database] Improved primary key detection in PostgreSQL data sync for roles that are not owners of synchronized table [#3606](https://gitlab.com/baserow/baserow/-/issues/3606)
* [Core] MCP server returns error response [#3615](https://gitlab.com/baserow/baserow/-/issues/3615)
* [Database] Fix for workspace export with default value on number field [#3619](https://gitlab.com/baserow/baserow/-/issues/3619)
* [Builder] Formula values are not emptied anymore when an error happens
* [Database] Don't create MCP tools for trashed databases.
* [Builder] Markdown content now follows application theme

### Refactors
* [Database] Improved group by ManyToMany (link row and multiple select) performance by using CTE.

### Breaking API changes
* [Database] Returns an HTTP 409 instead of an HTTP 503 when the request fails due to a deadlock.


## Released 1.33.2

### New features
* [Builder] Support id_token to get user info with OIDC providers

### Bug fixes
* [Database] Fix bug formatting numbers in the gallery view with space and comma. [#3584](https://gitlab.com/baserow/baserow/-/issues/3584)
* [Builder] Fixed a bug caused by an uninitialized variable. [#3589](https://gitlab.com/baserow/baserow/-/issues/3589)
* [Builder] Fix a potential race condition when querying Data Sources. [#3593](https://gitlab.com/baserow/baserow/-/issues/3593)
* [Database] Resolved a warning which was displayed when an autonumber field was added. [#3600](https://gitlab.com/baserow/baserow/-/issues/3600)

### Refactors
* [Core] Use cache for jest, eslint and prettier


## Released 1.33.1

### New features
* [Database] Fix Airtable import empty is_any_off bug. [#3595](https://gitlab.com/baserow/baserow/-/issues/3595)
* [Database] Show row creation/deletion in row history' [#2117](https://gitlab.com/baserow/baserow/-/issues/2117)
* [Database] Add empty and not_empty filters for lookup fields. [#3527](https://gitlab.com/baserow/baserow/-/issues/3527)
* [Database] Introduce advanced self-hosting license type.

### Bug fixes
* [Builder] Fixed bug that prevented older browsers from checking the error state of a Collection element. [#3591](https://gitlab.com/baserow/baserow/-/issues/3591)
* [Builder] Made the login error handling slightly more robust. [#3592](https://gitlab.com/baserow/baserow/-/issues/3592)
* [Builder] Improved error handling in user source authentication. [#3594](https://gitlab.com/baserow/baserow/-/issues/3594)
* [Database] Fix clearing link row and rating cell value in the grid view with backspace. [#1788](https://gitlab.com/baserow/baserow/-/issues/1788)

### Refactors
* [Database] Fix queuing and waiting many tableusageupdate queries [#2173](https://gitlab.com/baserow/baserow/-/issues/2173)


## Released 1.33.0

### New features
* [Database] Handle UniquePrimaryPropertyNotFound gracefully. [#3430](https://gitlab.com/baserow/baserow/-/issues/3430)
* [Database] Add support for list filtering on link_row_has filter type. [#3478](https://gitlab.com/baserow/baserow/-/issues/3478)
* [Database] Support default values for Boolean and Number fields [#2173](https://gitlab.com/baserow/baserow/-/issues/2173)
* [Builder] Add a file input element to upload files [#2188](https://gitlab.com/baserow/baserow/-/issues/2188)
* [Database] Install template during onboarding [#2638](https://gitlab.com/baserow/baserow/-/issues/2638)
* [Builder] Add rating element, collection rating field and rating input field. [#2765](https://gitlab.com/baserow/baserow/-/issues/2765)
* [Database] Add field level permisions. [#3189](https://gitlab.com/baserow/baserow/-/issues/3189)
* [Database] Trigger webhooks when linked row values change in related tables. [#3267](https://gitlab.com/baserow/baserow/-/issues/3267)
* [Builder] Add support for list type values for query parameters. [#3433](https://gitlab.com/baserow/baserow/-/issues/3433)
* [Builder] Add "Made with Baserow" label to bottom of the pages. [#3464](https://gitlab.com/baserow/baserow/-/issues/3464)
* [Database] Introduced MCP server. [#3556](https://gitlab.com/baserow/baserow/-/issues/3556)
* [Database] Introduce `exclude_count` API param to avoid counting rows when paginating data [#3560](https://gitlab.com/baserow/baserow/-/issues/3560)
* [Database] Optionally limit the number of relationships of a link to table field. [#403](https://gitlab.com/baserow/baserow/-/issues/403)
* [Core] Introduced step-by-step guided tour after creating an account.

### Bug fixes
* [Database] When grid is sorted, pasting values at the end of the grid will populate new rows instead of changing existing ones. [#1788](https://gitlab.com/baserow/baserow/-/issues/1788)
* [Database] Allow import GBs of data from Airtable. [#2712](https://gitlab.com/baserow/baserow/-/issues/2712)
* fixed asgi race condition when accessing auth.User.profile - do not expire model's Meta cache [#3346](https://gitlab.com/baserow/baserow/-/issues/3346)
* [Database] Fix date_is_within for dates in the past and adds more operators [#3366](https://gitlab.com/baserow/baserow/-/issues/3366)
* [Builder] Fix "number" validation for handling of decimal numbers with using comma or dot as decimal separator [#3408](https://gitlab.com/baserow/baserow/-/issues/3408)
* [Builder] Resolved an issue which caused table element actions to disappear when it was duplicated. [#3521](https://gitlab.com/baserow/baserow/-/issues/3521)
* [Database] Reduce deadlocks on rows endpoints [#3545](https://gitlab.com/baserow/baserow/-/issues/3545)
* [Builder] Resolved an issue which prevented pages with incomplete table element fields from being published properly. [#3547](https://gitlab.com/baserow/baserow/-/issues/3547)
* [Database] Fix an issue when converting from Quill to Markdown during Airtable import. [#3561](https://gitlab.com/baserow/baserow/-/issues/3561)
* [Database] Set empty value on cell(s) clear for text field with default value [#3568](https://gitlab.com/baserow/baserow/-/issues/3568)
* [Database] Fix export crash caused by formula fields with Invalid number and 0 decimal precision [#3573](https://gitlab.com/baserow/baserow/-/issues/3573)
* [Builder] Add `thisCalendarMonth` and `thisCalendarWeek` Airtable import filters.
* [Builder] Fixes the Airtable file import if not signed urls are in the payload.
* [Builder] Fix bug when deleting a duplicated menu element was deleting the initial actions
* [Database] Fix bug where it was not possible to create a row in an empty table with a group.
* [Database] Fix bug where the error page of a table not found page fails hard.
* [Database] Fixes validation error when a select option is added.
* [Database] Fixed bug where the backend fails hard if the filter value exceeds 255 characters.
* [Dashboard] Fix form validation issue when table changes
* [Database] Fix read_only field attributes for imported fields.
* [Builder] Resolved an issue which prevented logged-out users from previewing certain application templates
* [Builder] Resolved a create row workflow action error which presented itself when an invalid value was provided to a date field.

### Refactors
* [Dashboard] Move chart widget with its service to premium tier [#3544](https://gitlab.com/baserow/baserow/-/issues/3544)
* [Core] Implemented small styling changes for the collapsing of the left sidebar.
* [Core] Improve paid features modal by listing all the features.
* [Core] Redesigned the left sidebar of the modal.
* [Core] Reduce number of queries when fetching applications with RBAC.
* [Database] Updated form view styling.
* [Database] Updated gallery view styling.
* [Database] Updated grid view styling.
* [Database] Updated kanban view styling.
* [Database] Updated the header styling to match the latest Figma designs.
* [Core] Workspace template IDs query performance improvement.

### Breaking API changes
* [Database] Pagination now returns an empty list instead of "ERROR_INVALID_PAGE" when the page exceeds the maximum. [#3560](https://gitlab.com/baserow/baserow/-/issues/3560)


## Released 1.32.5

### Bug fixes
* [Core] Clear local_cache for celery tasks [#3528](https://gitlab.com/baserow/baserow/-/issues/3528)
* [Database] Fix broken continue button and validation of the onboarding import step.
* [Builder] Fix schema caching issue again

### Breaking API changes
* [Database] Updated Langchain, Gunicorn, and Django backend dependencies.


## Released 1.32.4

### New features
* [Database] Import Airtable gallery view. [#793](https://gitlab.com/baserow/baserow/-/issues/793)

### Bug fixes
* [Builder] Ensure that workflow action and user source forms disallow choose a data synced table. [#3104](https://gitlab.com/baserow/baserow/-/issues/3104)
* [Database] Fix issue with 'this_week' and 'next_week' operators in date filters [#3526](https://gitlab.com/baserow/baserow/-/issues/3526)
* [Database] Fix bug where the Airtable import crashes if the table has sections.
* [Builder] Fix cache invalidation on field change for data sources
* [Core] Record frontend sessions in Sentry if there is an error.

### Refactors
* [Builder] Integration endpoint doesn't return the table fields anymore to improve performance


## Released 1.32.3

### New features
* [Database] Optionally provide session authentication for Airtable import.
* [Core] Updated Posthog library and disabled session recording by default.

### Bug fixes
* [Database] Fix form meta controls validation.


## Released 1.32.2

### Bug fixes
* [Database] Fixed a bug where the filters of a created and updated by fields could not load all collaborators.


## Released 1.32.1

### Bug fixes
* [Database] Fixed a bug in which sorting by a link row field caused the frontend to crash. [#3522](https://gitlab.com/baserow/baserow/-/issues/3522)


## Released 1.32.0

### New features
* Add support for collaborator fields in form views. [#1554](https://gitlab.com/baserow/baserow/-/issues/1554)
* [Dashboard] Introduce dashboards with summary and chart widgets [#2206](https://gitlab.com/baserow/baserow/-/issues/2206)
* [Database] Introduce row update functionality during table import [#2213](https://gitlab.com/baserow/baserow/-/issues/2213)
* [Database] Add rows enter view webhook event type. [#3009](https://gitlab.com/baserow/baserow/-/issues/3009)
* [Core] Hide Baserow description in all emails if logo is changed. [#3066](https://gitlab.com/baserow/baserow/-/issues/3066)
* [Builder] Allow to customize table header filter/sort/search buttons [#3151](https://gitlab.com/baserow/baserow/-/issues/3151)
* [Builder] Introduced Saml and OpenID Connect authentication in the application builder. [#3167](https://gitlab.com/baserow/baserow/-/issues/3167)
* [Builder] Added a shortcut in the publishing modal so that domains can be created if an application doesn't yet have any. [#3170](https://gitlab.com/baserow/baserow/-/issues/3170)
* [Builder] Improve 'Add new element' modal. [#3172](https://gitlab.com/baserow/baserow/-/issues/3172)
* Add abilty to export files in grid [#3203](https://gitlab.com/baserow/baserow/-/issues/3203)
* Airtable import report. [#3263](https://gitlab.com/baserow/baserow/-/issues/3263)
* [Database] Show relationship changes (added or removed) in the related row's change history. [#3264](https://gitlab.com/baserow/baserow/-/issues/3264)
* Multiple collaborator field group by support. [#3447](https://gitlab.com/baserow/baserow/-/issues/3447)
* Airtable import field type improvements. [#3455](https://gitlab.com/baserow/baserow/-/issues/3455)
* [Builder] Added a container element to group multiple elements. [#3458](https://gitlab.com/baserow/baserow/-/issues/3458)
* [Builder] Improved the performance of published applications. [#3472](https://gitlab.com/baserow/baserow/-/issues/3472)
* [Builder] Added the Menu element. [#3477](https://gitlab.com/baserow/baserow/-/issues/3477)
* [Builder] Added theme setting to configure Link decoration. [#3515](https://gitlab.com/baserow/baserow/-/issues/3515)
* [Database] Introduced the ability to sort by single select option order. [#786](https://gitlab.com/baserow/baserow/-/issues/786)
* [Database] Import Airtable view colors. [#793](https://gitlab.com/baserow/baserow/-/issues/793)
* [Database] Import Airtable view filters. [#793](https://gitlab.com/baserow/baserow/-/issues/793)
* Import Airtable grid views, their sorts, group by, and field options. [#793](https://gitlab.com/baserow/baserow/-/issues/793)
* Add SegmentControl variants
* [Builder] Introduced a shortcut in the Login form configuration so that it's easier to create a new user source.
* Send notification to authorized user when periodic data sync is deactivated.
* Send notification to all admins when a webhook is deactivated.

### Bug fixes
* Preserve the precision of the currency field in the Airtable import. [#1058](https://gitlab.com/baserow/baserow/-/issues/1058)
* [Builder] Fixed element position resets on editing of it's properties [#2342](https://gitlab.com/baserow/baserow/-/issues/2342)
* Fix pasting markdown text into rich edit that resulted in unformatted markdown [#2383](https://gitlab.com/baserow/baserow/-/issues/2383)
* [Database] Fix select option values in row history after API changes [#2509](https://gitlab.com/baserow/baserow/-/issues/2509)
* [Database] Fixed a bug that prevented duplicating views filtered by a collaborator correctly. [#3017](https://gitlab.com/baserow/baserow/-/issues/3017)
* [Database] Fixed unscrollable timezone dropdown issue when creating/editing a field. [#3041](https://gitlab.com/baserow/baserow/-/issues/3041)
* [Database] Fix protected fields in the data sync forms. [#3191](https://gitlab.com/baserow/baserow/-/issues/3191)
* Database: when an error is returned by the backend, it will be shown inside of the body of the view, so user still have access to navigation interface. [#3331](https://gitlab.com/baserow/baserow/-/issues/3331)
* [Database] Fix issue with unexpected temperature argument passed to OpenAI messages.create [#3384](https://gitlab.com/baserow/baserow/-/issues/3384)
* [Database] Allow bigger image dimensions. [#3387](https://gitlab.com/baserow/baserow/-/issues/3387)
* Preserve the currency symbol and formatting of the currency field in Airtable import. [#3395](https://gitlab.com/baserow/baserow/-/issues/3395)
* Prevent view from updated state with data from wrong view when pending request completes. [#3398](https://gitlab.com/baserow/baserow/-/issues/3398)
* [Database] Fix for data sync failing when syncing baserow table with AIField [#3403](https://gitlab.com/baserow/baserow/-/issues/3403)
* Use BigIntegerField for ImportExportResource.size  [#3424](https://gitlab.com/baserow/baserow/-/issues/3424)
* [Builder] Fix updating of page parameters when URL query parameters change. [#3434](https://gitlab.com/baserow/baserow/-/issues/3434)
* [Database] Fix field formatting options in rollup fields targeting formula fields [#3443](https://gitlab.com/baserow/baserow/-/issues/3443)
* Fixed null check for query parameters in link URL generation [#3444](https://gitlab.com/baserow/baserow/-/issues/3444)
* [Database] Do not register jobs that have unknown job type in the job type in the registry. [#3447](https://gitlab.com/baserow/baserow/-/issues/3447)
* Fix for Secure File Serve with SSO SAML/OIDC authentication [#3449](https://gitlab.com/baserow/baserow/-/issues/3449)
* [Builder] Resolved a bug where creating an element with an invalid parent would raise an error. [#3452](https://gitlab.com/baserow/baserow/-/issues/3452)
* [Builder] Add page background color to theme block [#3457](https://gitlab.com/baserow/baserow/-/issues/3457)
* [Database] Updating a cell no longer fails when a view is sorted or grouped by a linked field whose primary field is a formula. [#3484](https://gitlab.com/baserow/baserow/-/issues/3484)
* [Database] Fix for creating snapshot triggers infinite loop for checking status update [#3490](https://gitlab.com/baserow/baserow/-/issues/3490)
* [Database] Allow change field type with active sort [#3519](https://gitlab.com/baserow/baserow/-/issues/3519)
* [Builder] Fix broken pagination after filtering collection elements
* [Builder] Fix crash when creating a builder application after deleting another one
* Fix error when syncing a table with a trashed field.
* [Database] Fix the progress bar percentage when importing applications into the workspace.

### Refactors
* Upgrade vuelidate [#2805](https://gitlab.com/baserow/baserow/-/issues/2805)
* [Builder] Improve data dispatching performances [#2978](https://gitlab.com/baserow/baserow/-/issues/2978)
* Reduce the number of queries when logging in or load Baserow. [#3364](https://gitlab.com/baserow/baserow/-/issues/3364)
* [Builder] Improve integration endpoint performances [#3418](https://gitlab.com/baserow/baserow/-/issues/3418)
* Lowered grid view minimum field with from 100 to 78. [#3428](https://gitlab.com/baserow/baserow/-/issues/3428)
* [Builder] Improved performance in preview mode
* Speed up database setup for tests


## Released 1.31.1

### Bug fixes
* [Builder] Resolved an issue in data source filters and sortings which prevented them from working correctly when the database field they were associated with were trashed. [#3378](https://gitlab.com/baserow/baserow/-/issues/3378)
* Fixed an issue where the notification mode settings were not displayed correctly if the row was not in the view. [#3411](https://gitlab.com/baserow/baserow/-/issues/3411)
* Disable optimistic updates for rows with filters, sorts, or group by on backend-calculated read-only fields. [#3415](https://gitlab.com/baserow/baserow/-/issues/3415)
* Fixed issue where collaborator names were not displayed in filter when scrolling or searching [#3431](https://gitlab.com/baserow/baserow/-/issues/3431)
* [Builder] Resolved an issue which prevented tables from paging correctly.
* Fix indentation bug where duplicate table entries were added.
* Fix iCal feed when the table has select_related fields from enhance_queryset.


## Released 1.31.0

### New features
* Allow optionally exporting in publicly shared views. [#1213](https://gitlab.com/baserow/baserow/-/issues/1213)
* Allow skipping files during Airtable import [#1225](https://gitlab.com/baserow/baserow/-/issues/1225)
* [Builder] Introducing query parameters [#1661](https://gitlab.com/baserow/baserow/-/issues/1661)
* [Builder] Ensure that sensitive Integration data is not exported. [#1863](https://gitlab.com/baserow/baserow/-/issues/1863)
* Add support for the Collaborator field type in formulas and lookups. [#1890](https://gitlab.com/baserow/baserow/-/issues/1890)
* [Builder] Enhance security by excluding unused fields from the Data Source context. [#3001](https://gitlab.com/baserow/baserow/-/issues/3001)
* Add distribution aggregation. [#3056](https://gitlab.com/baserow/baserow/-/issues/3056)
* [Builder] Added radius settings for Element background and border. [#3068](https://gitlab.com/baserow/baserow/-/issues/3068)
* [Builder] Add support for Custom Colors in Theme settings. [#3068](https://gitlab.com/baserow/baserow/-/issues/3068)
* [Builder] Add vertical and horizontal gap to Repeat Element. [#3068](https://gitlab.com/baserow/baserow/-/issues/3068)
* [Builder] Added the ability to set the Font Weight for various elements in the Theme settings. [#3068](https://gitlab.com/baserow/baserow/-/issues/3068)
* Periodic data sync [#3071](https://gitlab.com/baserow/baserow/-/issues/3071)
* Number lookup field filters [#3112](https://gitlab.com/baserow/baserow/-/issues/3112)
* Improve the export progress update [#3184](https://gitlab.com/baserow/baserow/-/issues/3184)
* Notify other windows about started jobs. [#3198](https://gitlab.com/baserow/baserow/-/issues/3198)
* Workspace context menu search [#3265](https://gitlab.com/baserow/baserow/-/issues/3265)
* Optionally allow choosing view in the local Baserow table data sync. [#3266](https://gitlab.com/baserow/baserow/-/issues/3266)
* Add support to filter lookup of multiple select fields. [#3277](https://gitlab.com/baserow/baserow/-/issues/3277)
* Added support for filtering lookups of date fields. [#3362](https://gitlab.com/baserow/baserow/-/issues/3362)
* Add filter support for formula referencing a multiple collaborator field. [#3400](https://gitlab.com/baserow/baserow/-/issues/3400)
* Add button xlarge type variant.
* [Builder] Focus search input when opening add element modal

### Bug fixes
* Fix invalid regular expression error raised when creating a formula with an invalid regex [#1053](https://gitlab.com/baserow/baserow/-/issues/1053)
* Fix formula issue with lookup and UUID as primary field [#1867](https://gitlab.com/baserow/baserow/-/issues/1867)
* Fix formula issue with lookup and UUID as primary field [#2354](https://gitlab.com/baserow/baserow/-/issues/2354)
* Fix import/export/snapshot issue with broken formulas [#2711](https://gitlab.com/baserow/baserow/-/issues/2711)
* Validate request.data before views reaching to .data early [#2740](https://gitlab.com/baserow/baserow/-/issues/2740)
* [Builder] Fix worfklow action navigation for pages with no parameters [#2833](https://gitlab.com/baserow/baserow/-/issues/2833)
* Fix issue with text changing position when renaming items in the sidebar [#2883](https://gitlab.com/baserow/baserow/-/issues/2883)
* Display progress of pending jobs in the sidebar when the workspace is empty [#2904](https://gitlab.com/baserow/baserow/-/issues/2904)
* Fix is empty/not empty filter behavior for single select field with deleted options [#3053](https://gitlab.com/baserow/baserow/-/issues/3053)
* [Builder] Filter out unused fields from dispatched Workflow Actions. [#3090](https://gitlab.com/baserow/baserow/-/issues/3090)
* Restore decoration value ids during table import [#3193](https://gitlab.com/baserow/baserow/-/issues/3193)
* Allow editors to subscribe to a form view. [#3271](https://gitlab.com/baserow/baserow/-/issues/3271)
* Fix crash when invalid value is passed to link row fields with read-only primary field in the linked table. [#3277](https://gitlab.com/baserow/baserow/-/issues/3277)
* Long text in full text search overflows window content. [#3285](https://gitlab.com/baserow/baserow/-/issues/3285)
* [Builder] Resolved an error triggered when a workflow action would attempt to write or update a row pointing to a date field with an invalid value. [#3286](https://gitlab.com/baserow/baserow/-/issues/3286)
* [Builder] Resolved an issue with the 'refresh data source' action when the data source was shared across multiple pages. [#3308](https://gitlab.com/baserow/baserow/-/issues/3308)
* Count/Rollup fields will reset through_field when recalculating linked row field removal [#3309](https://gitlab.com/baserow/baserow/-/issues/3309)
* Fix a bug causing the backend to fail hard when sorting by an AI Field. [#3310](https://gitlab.com/baserow/baserow/-/issues/3310)
* Fix Airtable import failing if the 'foreignRowId' key is missing. [#3317](https://gitlab.com/baserow/baserow/-/issues/3317)
* [Builder] Fixed a bug that caused an error during export when the application had a background image in the page section of the theme. [#3320](https://gitlab.com/baserow/baserow/-/issues/3320)
* [Builder] Resolved an error which was thrown when a data source's integration was destroyed. [#3323](https://gitlab.com/baserow/baserow/-/issues/3323)
* [Builder] Resolved a styling issue in the Link element, and the Table element link type when swapping between link and button variants. [#3325](https://gitlab.com/baserow/baserow/-/issues/3325)
* Fix an issue with frontend when looking up formatted number fields. [#3332](https://gitlab.com/baserow/baserow/-/issues/3332)
* [Builder] Allow children of Header and Footer elements to set their width. [#3333](https://gitlab.com/baserow/baserow/-/issues/3333)
* Fix field settings suggestions for lookup and formula fields. [#3336](https://gitlab.com/baserow/baserow/-/issues/3336)
* Fix a bug causing the frontend to crash when trying to hide fields directly after creating a timeline. [#3358](https://gitlab.com/baserow/baserow/-/issues/3358)
* [Builder] Fixed bug that caused a workspace import to fail when certain fields were missing. [#3375](https://gitlab.com/baserow/baserow/-/issues/3375)
* Exclude Link to table fields dependencies from periodic updates [#3379](https://gitlab.com/baserow/baserow/-/issues/3379)
* [Builder] Resolved a bug in filtered table elements which prevented their workflow actions from dispatching properly. [#3399](https://gitlab.com/baserow/baserow/-/issues/3399)
* Fix broken Heroku addons and one-click-deploy button URL. [#3401](https://gitlab.com/baserow/baserow/-/issues/3401)
* Fix backend/frontend formula sort differences. [#3410](https://gitlab.com/baserow/baserow/-/issues/3410)
* [Builder] Fix children element style in element menu when the container is selected [#3420](https://gitlab.com/baserow/baserow/-/issues/3420)
* [Builder] Fix issue when previewing templates in some situations [#3421](https://gitlab.com/baserow/baserow/-/issues/3421)
* [Builder] Fix failing delete action
* [Builder] Resolved an error which prevented 'summarize field' data sources from being used.
* Fix dashboard no workspace translations
* Fix publicly shared view URL not always visible because it does't fit.
* Remove checkbox line-height

### Refactors
* Upgrade vue-chartjs from 4.x to 5.x [#1683](https://gitlab.com/baserow/baserow/-/issues/1683)
* Code cleanup for advanced number formatting [#3293](https://gitlab.com/baserow/baserow/-/issues/3293)
* Add user id to sentry issues. [#3338](https://gitlab.com/baserow/baserow/-/issues/3338)
* [Builder] Improve element selection performance when there are many elements
* Improve field dependency rebuild by doing operations in bulk.
* Improve lookup rebuild from field names method performance.
* Improve view field change type performance by doing update in bulk.
* Various small query performance improvements related to deleting and updating fields.

### Breaking API changes
* Remove support for PostgreSQL 11. [#3371](https://gitlab.com/baserow/baserow/-/issues/3371)


## Released 1.30.1

### Bug fixes
* Non-standard image formats don't break thumbnails [#2745](https://gitlab.com/baserow/baserow/-/issues/2745)
* handle null payload for file field [#2906](https://gitlab.com/baserow/baserow/-/issues/2906)
* Fix search for number field with applied formating [#3292](https://gitlab.com/baserow/baserow/-/issues/3292)
* Fix a bug that prevent a database index to be created when sorting/grouping by a duration field. [#3296](https://gitlab.com/baserow/baserow/-/issues/3296)
* Fix admin dashboard translations
* Fix loading non en and fr translations for premium and enterprise in production mode.
* Fix API docs server side rendering bugs.


## Released 1.30.0

### New features
* Add support for advanced number formatting [#1270](https://gitlab.com/baserow/baserow/-/issues/1270)
* Add ability to group by link to table field. [#2306](https://gitlab.com/baserow/baserow/-/issues/2306)
* [Builder] Improve Builder security with Page level Visibility. [#2392](https://gitlab.com/baserow/baserow/-/issues/2392)
* Select row modal field width, order, and visibility configuration. [#2439](https://gitlab.com/baserow/baserow/-/issues/2439)
* [Builder] Add the multi-page header and footer containers [#2486](https://gitlab.com/baserow/baserow/-/issues/2486)
* [Builder] Add date time picker element [#2625](https://gitlab.com/baserow/baserow/-/issues/2625)
* [Builder] UX improvements: defaults for theme inputs, optional hash prefix in hex color inputs, and padding in Theme page. [#3067](https://gitlab.com/baserow/baserow/-/issues/3067)
* Introduced ability to configure exising data sync. [#3072](https://gitlab.com/baserow/baserow/-/issues/3072)
* Duration formula field filters [#3110](https://gitlab.com/baserow/baserow/-/issues/3110)
* HubSpot contacts data sync. [#3119](https://gitlab.com/baserow/baserow/-/issues/3119)
* Provide alias names for field types to search for in the dropdown list. [#3179](https://gitlab.com/baserow/baserow/-/issues/3179)
* Export table/view to Excel file [#324](https://gitlab.com/baserow/baserow/-/issues/324)
* [Builder] Display a count of user source users in the application settings panel. [#3251](https://gitlab.com/baserow/baserow/-/issues/3251)
* Collapse sidebar with button [#3258](https://gitlab.com/baserow/baserow/-/issues/3258)
* OpenRouter.ai generative AI integration. [#3259](https://gitlab.com/baserow/baserow/-/issues/3259)
* Add support to filter multiple select formula fields. [#3276](https://gitlab.com/baserow/baserow/-/issues/3276)
* Add ability to sort by link_row ('Link to table') field [#506](https://gitlab.com/baserow/baserow/-/issues/506)
* Allow choosing select options in the form view. [#814](https://gitlab.com/baserow/baserow/-/issues/814)
* Add sort and group by add field search.
* Added Korean language and translations
* Dependant field lookup performance improvement by per database pre-filtering.
* Introduced health check endpoints for the celery queue size.

### Bug fixes
* [Builder] Fixed a bug in the Create/Update row workflow action when concatenating a formula field and a string. [#2546](https://gitlab.com/baserow/baserow/-/issues/2546)
* [Builder] Fixed an error that triggers when adding a new row in the Data Source modal for the Link to Table field. [#2579](https://gitlab.com/baserow/baserow/-/issues/2579)
* [Builder] Resolved an issue where the data source name uniqueness wasn't handled properly. [#3149](https://gitlab.com/baserow/baserow/-/issues/3149)
* [Builder] Resolved an issue with changing a data source's table and view at the same time. [#3200](https://gitlab.com/baserow/baserow/-/issues/3200)
* Resolved an issue in our Local Baserow integration filters where they would sometimes be incompatible with a changed field type. [#3226](https://gitlab.com/baserow/baserow/-/issues/3226)
* [Builder] Resolves an error raised when a collection element, using a single row data source, finds that its property has been trashed. [#3245](https://gitlab.com/baserow/baserow/-/issues/3245)
* Fix for undefined field being passed to getFieldWidth  [#3248](https://gitlab.com/baserow/baserow/-/issues/3248)
* Handle properly fetching list of files in archive for zipfile and zipstream [#3249](https://gitlab.com/baserow/baserow/-/issues/3249)
* [Builder] Fix inconsistent borders in table element [#3250](https://gitlab.com/baserow/baserow/-/issues/3250)
* [Builder] Resolved an issue with publishing an application containing a 'summarize field' data source. [#3255](https://gitlab.com/baserow/baserow/-/issues/3255)
* [Builder] Fix bug where publishing the builder could sometimes raise an error. [#3278](https://gitlab.com/baserow/baserow/-/issues/3278)
* [Builder] Resolved an issue with changing a 'summarize field' data source into a different type of data source. [#3281](https://gitlab.com/baserow/baserow/-/issues/3281)
* [Builder] Optimize FormInput component to ensure duplicate requests are not made on blur. [#3283](https://gitlab.com/baserow/baserow/-/issues/3283)
* undefined baserow.core.generative_ai.generative_ai_model_types.OpenAIGenerativeAIModelType.prompt_with_files local vars fixed
* [Builder] Add theme support to date and time picker element label
* Fix API Docs view layout
* Fix some frontend props defaults values for objects.
* Show accidentally removed callback URL for the OpenID Connect settings form again.
* Fixed boolean filter with null filter value
* Resolved a checkbox display issue which presented itself when multiple checkboxes were displayed on the same page.
* Resolved an accidental regression when an exact date filter is applied to a date field.

### Refactors
* Use ZipStream for creating export file [#3229](https://gitlab.com/baserow/baserow/-/issues/3229)
* [Builder] Improved how collection elements are exported and imported when data they rely on has been deleted. [#3241](https://gitlab.com/baserow/baserow/-/issues/3241)
* Moved instance admin dashboard, user, and workspace to the open source core. [#3241](https://gitlab.com/baserow/baserow/-/issues/3241)


## Released 1.29.3

### New features
* Prevents webhook call tasks piling up if many webhooks are triggered. [#2758](https://gitlab.com/baserow/baserow/-/issues/2758)
* Prevent triggering webhook if query param is provided on row create update or delete endpoints [#3085](https://gitlab.com/baserow/baserow/-/issues/3085)
* limit logging sign in actions [#3206](https://gitlab.com/baserow/baserow/-/issues/3206)

### Bug fixes
* Fix a bug where setting the User Role field to a Formula field could raise an error. [#3190](https://gitlab.com/baserow/baserow/-/issues/3190)
* Fix for prefill values are lost for password protected forms [#3194](https://gitlab.com/baserow/baserow/-/issues/3194)
* Fix form view conditions groups export import [#3232](https://gitlab.com/baserow/baserow/-/issues/3232)
* Fix password protected shared view login page
* Remove login view vertical scrollbar on Safari iOS

### Refactors
* Redesigned auth views [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)


## Released 1.29.2

### New features
* Boolean lookup filters: empty/not empty/none of/any/all [#3103](https://gitlab.com/baserow/baserow/-/issues/3103)
* Copy cells as rich text table and optionally include header.

### Bug fixes
* Fix bug by include schema in PostgreSQL data sync.
* Fix corrupted export being created on s3 like storages [#3197](https://gitlab.com/baserow/baserow/-/issues/3197)
*  Fix import/export support for larger files on s3-like storages [#3202](https://gitlab.com/baserow/baserow/-/issues/3202)
* [Builder] Fix bug when dispatching a data source with a deleted field


## Released 1.29.1

### Bug fixes
* Make import workspace applications icon consistent [#3187](https://gitlab.com/baserow/baserow/-/issues/3187)
* [Builder] Resolved an issue where the API would throw an error if a 'summarize field' data source is saved with a field, but no aggregation.
* Fix export for S3-like storages.


## Released 1.29.0

### New features
* Use backend and frontend matching collate sort for single select, multiple select, and multiple collaborators field types. [#1944](https://gitlab.com/baserow/baserow/-/issues/1944)
* [Builder] Only return Data Source field data when used by a formula in a Page. [#2063](https://gitlab.com/baserow/baserow/-/issues/2063)
* [Builder] Allow sharing data sources across pages [#2486](https://gitlab.com/baserow/baserow/-/issues/2486)
* [Builder] Allow collection elements to be filtered, sorted and searched against. [#2516](https://gitlab.com/baserow/baserow/-/issues/2516)
* Add Anthropic AI integration. [#2564](https://gitlab.com/baserow/baserow/-/issues/2564)
* Allow to limit concurency for uvicorn workers in asgi backend. [#2773](https://gitlab.com/baserow/baserow/-/issues/2773)
* Allow exporting workspace applications [#2930](https://gitlab.com/baserow/baserow/-/issues/2930)
* Allow importing workspace applications [#2951](https://gitlab.com/baserow/baserow/-/issues/2951)
* Allow settings temperature in AI field and AI formula generation. [#3060](https://gitlab.com/baserow/baserow/-/issues/3060)
* [Builder] Introducing the new row aggregations service to the application builder. [#3069](https://gitlab.com/baserow/baserow/-/issues/3069)
* Baserow table data sync single select field compatibility. [#3074](https://gitlab.com/baserow/baserow/-/issues/3074)
* Jira issues data sync. [#3075](https://gitlab.com/baserow/baserow/-/issues/3075)
* GitLab issues data sync. [#3076](https://gitlab.com/baserow/baserow/-/issues/3076)
* GitHub issues data sync. [#3077](https://gitlab.com/baserow/baserow/-/issues/3077)
* PostgreSQL data sync. [#3079](https://gitlab.com/baserow/baserow/-/issues/3079)
* Added progress to the data sync. [#3075](https://gitlab.com/baserow/baserow/-/issues/3075)
* url formula field type filtering [#3111](https://gitlab.com/baserow/baserow/-/issues/3111)
* Mistral AI integration. [#3141](https://gitlab.com/baserow/baserow/-/issues/3141)
* AI choice output type for classification purposes. [#3143](https://gitlab.com/baserow/baserow/-/issues/3143)
* Add ability to change attributes in SAML response payload. [#3155](https://gitlab.com/baserow/baserow/-/issues/3155)
* Add CLI command for managing public keys for trusted sources [#3173](https://gitlab.com/baserow/baserow/-/issues/3173)
* Add new limit settings for import export workspace applications [#3180](https://gitlab.com/baserow/baserow/-/issues/3180)
* Add collaborate badge UI component
* Add filters support for formula referencing a single select field. [#3174](https://gitlab.com/baserow/baserow/-/issues/3174)
* Add filters support for lookups of single select fields. [#3182](https://gitlab.com/baserow/baserow/-/issues/3182)
* Added indicator next to the view name in the header.
* Show summary label in the footer of the grid view.

### Bug fixes
* Increase `max_length` for `submit_action_redirect_url` and fix validation. [#2018](https://gitlab.com/baserow/baserow/-/issues/2018)
* Keep AI field field ID references when duplicating table. [#2747](https://gitlab.com/baserow/baserow/-/issues/2747)
* FieldType.prepare_db_value validates arbitrary values in fields [#2768](https://gitlab.com/baserow/baserow/-/issues/2768)
* [Builder] Fix reactivity issue when deleting user source [#2867](https://gitlab.com/baserow/baserow/-/issues/2867)
* Form field condition groups restored on export/import [#2981](https://gitlab.com/baserow/baserow/-/issues/2981)
* Include the field description in export/import [#3022](https://gitlab.com/baserow/baserow/-/issues/3022)
* [Builder] Prevent excessive API requests in collection elements [#3028](https://gitlab.com/baserow/baserow/-/issues/3028)
* Fixes problem where AI field loading state didn't persist when it left the button. [#3039](https://gitlab.com/baserow/baserow/-/issues/3039)
* Fix a bug causing the UI to crash with an error message when creating a gallery view with an image from a lookup field. [#3059](https://gitlab.com/baserow/baserow/-/issues/3059)
* [Builder] Resolved an issue with removing a search query from a data source after one had been set. [#3092](https://gitlab.com/baserow/baserow/-/issues/3092)
* password fields are not searchable [#3093](https://gitlab.com/baserow/baserow/-/issues/3093)
* handle missing value key in adhoc filters [#3101](https://gitlab.com/baserow/baserow/-/issues/3101)
* [Builder] Ensure that the field name associated with a Repeat Element's schema_property is extracted. [#3136](https://gitlab.com/baserow/baserow/-/issues/3136)
* Resolved an API documentation mistake which incorrectly stated that application endpoints return views, they do not. [#3139](https://gitlab.com/baserow/baserow/-/issues/3139)
* Fix for primary field becomes invisible when set to a hidden field in grid view [#3168](https://gitlab.com/baserow/baserow/-/issues/3168)
* Resolved an issue with exporting workspace applications when a color decoration pointed to a single select option. [#3177](https://gitlab.com/baserow/baserow/-/issues/3177)
* Don't export deleted relations for link row fields. [#3183](https://gitlab.com/baserow/baserow/-/issues/3183)
* Fix a bug causing the related row modal to always use the slow compat search instead of the default one. [#3186](https://gitlab.com/baserow/baserow/-/issues/3186)
* [Builder] Fix broken data source for published website when using some field types in the table
* [Builder] Fix record selector name and option suffix formula resolution bug
* [Builder] Resolved an issue with creating and updating rows in workflow actions.
* Disable webhook type fields if not selected.
* Fix a bug causing an error importing the templates.
* Fix AI form and validation
* Fix Baserow table data sync export import authorized user and source table bug.
* fix dropdown padding
* Fix license check when exporting audit log from workspace as non-staff.
* Fix showing warning is staff checkbox in user admin form.
* Fix row metadata reactivity bug.
* Prevent Posthog page view of sensitive pages.

### Refactors
* [Builder] Improve how Element placeholder text is displayed in Editor, Preview, and Published views. [#2916](https://gitlab.com/baserow/baserow/-/issues/2916)
* [Builder] Create, update and delete workflow actions will now appear in the audit log.
* Properly build the download link for the DownloadLink frontend component.

### Breaking API changes
* Deprecate Postgresql v12.


## Released 1.28.0

### New features
* Add the timeline view. [#1262](https://gitlab.com/baserow/baserow/-/issues/1262)
* Allow to filter calendar view [#1633](https://gitlab.com/baserow/baserow/-/issues/1633)
* Add data sync backend. [#2278](https://gitlab.com/baserow/baserow/-/issues/2278)
* Introduced create data sync table frontend. [#2278](https://gitlab.com/baserow/baserow/-/issues/2278)
* Introduced the ability to sync with a local Baserow table. [#2278](https://gitlab.com/baserow/baserow/-/issues/2278)
* Optionally prevent sending row realtime update signals. [#2278](https://gitlab.com/baserow/baserow/-/issues/2278)
* Introduced read_only, immutable_type, and immutable_properties state for the field. [#2278](https://gitlab.com/baserow/baserow/-/issues/2278)
* Introduced the ability to manually trigger a sync. [#2278](https://gitlab.com/baserow/baserow/-/issues/2278)
* [Builder] Add related record selector element [#2396](https://gitlab.com/baserow/baserow/-/issues/2396)
* Allow to cancel a job (i.e. a database snapshot). [#2756](https://gitlab.com/baserow/baserow/-/issues/2756)
* [Builder] Add link/button variant to table element links [#2767](https://gitlab.com/baserow/baserow/-/issues/2767)
* Trigger row update webhook only when chosen field cell value changes. [#2877](https://gitlab.com/baserow/baserow/-/issues/2877)
* Introduced configurable row height in the grid view. [#340](https://gitlab.com/baserow/baserow/-/issues/340)
* Introduced view and filter created, updated, and deleted webhooks.

### Bug fixes
* [Builder] Automatic cast values for local baserow integration actions [#2542](https://gitlab.com/baserow/baserow/-/issues/2542)
* [Builder] Restore refresh token endpoint for published websites [#2631](https://gitlab.com/baserow/baserow/-/issues/2631)
* [Builder] Ensure that the create and update row workflow actions can resolve a formula referring to a current record's index. [#2735](https://gitlab.com/baserow/baserow/-/issues/2735)
* Fix Aggregations do not filter records in public shared views [#2760](https://gitlab.com/baserow/baserow/-/issues/2760)
* [Builder] Fix permission denied in preview when dispatching an action of an element visible only to loggued out visitors [#2912](https://gitlab.com/baserow/baserow/-/issues/2912)
* [Builder] Fix bug where ordering of List Rows and Get Rows service types could be inconsistent. [#2964](https://gitlab.com/baserow/baserow/-/issues/2964)
* [Builder] Tweaked the data source filter input styles. [#2967](https://gitlab.com/baserow/baserow/-/issues/2967)
* [Builder] Ensure that navigating to the current page doesn't cause an error. [#2973](https://gitlab.com/baserow/baserow/-/issues/2973)
* [Builder] Fix Choice element error when using integer as option value [#2977](https://gitlab.com/baserow/baserow/-/issues/2977)
* Fix selecting more than 120 rows when triggering AI value generation. [#2979](https://gitlab.com/baserow/baserow/-/issues/2979)
* [Builder] Allow email address to be case insensitive during login. [#2989](https://gitlab.com/baserow/baserow/-/issues/2989)
* Fix text wrapping for longer toast messages [#2998](https://gitlab.com/baserow/baserow/-/issues/2998)
* [Builder] Fix bug where calculating missingIndexes could sometimes raise a TypeError. [#3004](https://gitlab.com/baserow/baserow/-/issues/3004)
* Fix webhook list crashing if call response is empty. [#3024](https://gitlab.com/baserow/baserow/-/issues/3024)
* Fix survey mode view with rich text by not automatically focussing. [#3025](https://gitlab.com/baserow/baserow/-/issues/3025)
* [Builder] Ensure that data source filters can be imported and exported across workspaces when they contain single select options. [#3029](https://gitlab.com/baserow/baserow/-/issues/3029)
* [Builder] Fix record selector bug when using a data source sort [#3030](https://gitlab.com/baserow/baserow/-/issues/3030)
* [Builder] Safely check if property selector is available. [#3033](https://gitlab.com/baserow/baserow/-/issues/3033)
* Fixed a problem that caused form creation to be disabled for unsynced tables [#3051](https://gitlab.com/baserow/baserow/-/issues/3051)
* Handle long radio label [#3052](https://gitlab.com/baserow/baserow/-/issues/3052)
* [Builder] Resolved an issue where a table element's form would not display its columns if the table had no content. [#3055](https://gitlab.com/baserow/baserow/-/issues/3055)
* [Builder] Ensure that database applications are imported before builder applications. Resolved an issue where a nested repeat element's field was not migrated properly when imported into a new workspace. [#3057](https://gitlab.com/baserow/baserow/-/issues/3057)
* Fix a bug causing the backend to fail hard when creating a `user is` view filter with a non-digit filter value. [#3061](https://gitlab.com/baserow/baserow/-/issues/3061)
* Fix a bug causing Tab navigation to not work properly with forms in Survey mode. [#3064](https://gitlab.com/baserow/baserow/-/issues/3064)
* [Builder] Fix application builder template broken as soon as an element was selected
* Fix broken links in our website docs
* [Builder] Make empty data sources content less cramped

### Refactors
* Removed the deprecated webhook event types. [#2547](https://gitlab.com/baserow/baserow/-/issues/2547)
* Use dblclick event instead of checking ellapsed time for double-click. [#2628](https://gitlab.com/baserow/baserow/-/issues/2628)
* Upgrade to Django 5.X [#2864](https://gitlab.com/baserow/baserow/-/issues/2864)
* [Builder] Allow more elements to be nested in the column, form and repeat elements. [#2972](https://gitlab.com/baserow/baserow/-/issues/2972)


## Released 1.27.2

### Bug fixes
* Fix a bug causing the import to crash when a Count, a Rollup or Lookup field has some broken references. [#2961](https://gitlab.com/baserow/baserow/-/issues/2961)
* [Builder] Fix missing current record data in data explorer for table button events [#2962](https://gitlab.com/baserow/baserow/-/issues/2962)
* Fix bug with formulas and empty workspace when creating a snapshot.

### Refactors
* Limit the bulk update to only include fields that have been updated.


## Released 1.27.1

### Bug fixes
* Revert a change causing the `is` condition filter to be unavailable for numeric and text formulas. [#2848](https://gitlab.com/baserow/baserow/-/issues/2848)
* Fix a bug causing a formula referencing a link to a table not updating properly when the primary field changes. [#2856](https://gitlab.com/baserow/baserow/-/issues/2856)
* [Builder] Allow Integer as a valid Option Value for Choice Element when referencing a linked table. [#2910](https://gitlab.com/baserow/baserow/-/issues/2910)
* Fixed a bug causing the link_row_has_not view filter to not return the correct rows. [#2948](https://gitlab.com/baserow/baserow/-/issues/2948)


## Released 1.27.0

### New features
* Allow changing the primary field. [#1301](https://gitlab.com/baserow/baserow/-/issues/1301)
* Introduced official Helm chart. [#1728](https://gitlab.com/baserow/baserow/-/issues/1728)
* [premium] Calendar view can be shared with external applications via ical feed url [#1911](https://gitlab.com/baserow/baserow/-/issues/1911)
  * added `BASEROW_ICAL_VIEW_MAX_EVENTS` setting to limit amount of events in the output
* Allow typing immediately in the grid for link row cell to search for a relationship. [#193](https://gitlab.com/baserow/baserow/-/issues/193)
* Reduce the frequency of periodic field updates for unused workspaces. [#2120](https://gitlab.com/baserow/baserow/-/issues/2120)
* Allow selecting multiple relationships in the row select modal of the link row field. [#2267](https://gitlab.com/baserow/baserow/-/issues/2267)
* Join additional fields of a relationship via the API without creating a lookup field [#2460](https://gitlab.com/baserow/baserow/-/issues/2460)
* [Builder] Made it easier for application builder page designers to disable fields in their create/update row actions. [#2620](https://gitlab.com/baserow/baserow/-/issues/2620)
* Add onboarding step that adds fields to the created table [#2639](https://gitlab.com/baserow/baserow/-/issues/2639)
* [Builder] Allow collection elements to be nested in one another. It is now possible to nest a repeat in a repeat, or a table within a repeat.  [#2658](https://gitlab.com/baserow/baserow/-/issues/2658)
* Display hyperlinks in lookup fields when lookup field is URLField [#2692](https://gitlab.com/baserow/baserow/-/issues/2692)
* Show the Baserow version in the setting page. [#2696](https://gitlab.com/baserow/baserow/-/issues/2696)
* Add array filters for formula arrays based on text [#2727](https://gitlab.com/baserow/baserow/-/issues/2727)
* [Builder] Add image collection field to table elements [#2759](https://gitlab.com/baserow/baserow/-/issues/2759)
* [Builder] Improve data explorer performances and allow to select any repetition from a source [#2762](https://gitlab.com/baserow/baserow/-/issues/2762)
* Add tourl formula to support operations on url field type [#2791](https://gitlab.com/baserow/baserow/-/issues/2791)
* [Builder] Allow to change input elements style [#2803](https://gitlab.com/baserow/baserow/-/issues/2803)
* [Builder] Allow to configure table field styles [#2803](https://gitlab.com/baserow/baserow/-/issues/2803)
* [Builder] Allow to style the table element [#2803](https://gitlab.com/baserow/baserow/-/issues/2803)
* Extend array filters to support lookups of URL, email, phone number, and UUID fields [#2819](https://gitlab.com/baserow/baserow/-/issues/2819)
* [Builder] Introduce the 'delete row' workflow action [#2822](https://gitlab.com/baserow/baserow/-/issues/2822)
* Automatically prefill reverse relationship for new row in linked table [#2825](https://gitlab.com/baserow/baserow/-/issues/2825)
* Introduced arrow key navigation in the row select modal.
* Automatically start Storybook in the dev environment.
* [Builder] Introduced a checkbox to the repeat element form so that repetitions can be temporarily paused in the editor.
* Horizontal resize sidebar
* Introduced a neutral switch color.
* Replaced the dashboard with a workspace specific homepage.
* Redesigned the left sidebar.
* User admin: search for id, prevent unnecessary refresh, and add scrollbar expand list context

### Bug fixes
* Fix highlight of active menu item in API docs. [#2573](https://gitlab.com/baserow/baserow/-/issues/2573)
* [Builder] Fix bug where some child elements that should have been excluded by the Permission Manager were being returned in the queryset. [#2601](https://gitlab.com/baserow/baserow/-/issues/2601)
* Grid view: highlight edited row [#2690](https://gitlab.com/baserow/baserow/-/issues/2690)
* [Builder] Fix bug where changing Data Source type from 'Get multiple rows' to 'Get single row' could sometimes cause problems with exporting and duplicating the application. [#2730](https://gitlab.com/baserow/baserow/-/issues/2730)
* Cut off long relationship descriptions [#2742](https://gitlab.com/baserow/baserow/-/issues/2742)
* Properly handle user_field_names in api calls [#2784](https://gitlab.com/baserow/baserow/-/issues/2784)
* Fix nested filter group duplication. [#2788](https://gitlab.com/baserow/baserow/-/issues/2788)
* Fixed undefined variable in JobHandler.run [#2796](https://gitlab.com/baserow/baserow/-/issues/2796)
* [Builder] Fix filter data source formula fields alignment [#2804](https://gitlab.com/baserow/baserow/-/issues/2804)
* Clear workspace_id after each test [#2815](https://gitlab.com/baserow/baserow/-/issues/2815)
* Fix translation in SAML configuration [#2830](https://gitlab.com/baserow/baserow/-/issues/2830)
* [Builder] Fixed bug where typing too quickly in the Color style input caused duplicate characters. [#2831](https://gitlab.com/baserow/baserow/-/issues/2831)
* Fix upserts for table usage [#2839](https://gitlab.com/baserow/baserow/-/issues/2839)
* Update plugin boilerplate deps. [#2846](https://gitlab.com/baserow/baserow/-/issues/2846)
* [Builder] Fix theme panel opening on some screen resolution or when using browser zoom [#2853](https://gitlab.com/baserow/baserow/-/issues/2853)
* [Builder] Resolved an issue where removing an integration from a user source would raise an error when its users are listed. [#2861](https://gitlab.com/baserow/baserow/-/issues/2861)
* Fix a bug where the clear button doesn't work in workspace level audit logs. [#2866](https://gitlab.com/baserow/baserow/-/issues/2866)
* Prevent unnecessary $set events in Posthog [#2868](https://gitlab.com/baserow/baserow/-/issues/2868)
* [Builder] Fix bug where deleting a User Source would cause the frontend to crash. [#2869](https://gitlab.com/baserow/baserow/-/issues/2869)
* [Builder] Resolved an issue with refreshing a user source token when the table it's associated with has been trashed. [#2873](https://gitlab.com/baserow/baserow/-/issues/2873)
* Fixed a bug causing an issue reordering databases in workspace if user has editor or lower access on any database. [#2874](https://gitlab.com/baserow/baserow/-/issues/2874)
* Fixed a bug where calendar views did not reset the `date_field_id` when the associated date field was deleted. [#2881](https://gitlab.com/baserow/baserow/-/issues/2881)
* Display newly created linked row [#2901](https://gitlab.com/baserow/baserow/-/issues/2901)
* list rows via api fails with include or exclude and view_id [#2903](https://gitlab.com/baserow/baserow/-/issues/2903)
* Fix a bug causing dropdowns to not always work in forms when searching for an item. [#2929](https://gitlab.com/baserow/baserow/-/issues/2929)
* Update helm chart docs [#2936](https://gitlab.com/baserow/baserow/-/issues/2936)
* Create an ActionType for form submissions to track them in the audit log. [#2938](https://gitlab.com/baserow/baserow/-/issues/2938)
* Fix a bug causing every snapshot to perform additional queries to check permissions for RBAC. [#2941](https://gitlab.com/baserow/baserow/-/issues/2941)
* Fix date filter input [#2945](https://gitlab.com/baserow/baserow/-/issues/2945)
* Fix posthog error when user is an AnonymousUser and distinc_id is None. [#2954](https://gitlab.com/baserow/baserow/-/issues/2954)
* Fix import for broken lookup fields [#2955](https://gitlab.com/baserow/baserow/-/issues/2955)
* [Builder] Button click action were unable to access the current record values
* [Builder] Fix broken navigation or login after application pulication with modified user source
* [Builder] Hide builder application to roles other than Builder
* [Builder] improve performance when editing default value of input element inside repeat element
* [Builder] The `value` property was missing for lookup fields in the data explorer
* Fix clickable link in the URL field in the row edit modal. [#2804](https://gitlab.com/baserow/baserow/-/issues/2804)
* [Builder] Fix IFrame element source type selector
* Fixed broken OpenID Connect base_url validation.
* Fix pagination loading animation in the row select modal.
* Improved thread safety when generating models.
* Fix bug where the single select is any of values were not duplicated.
* Fix loading webhooks when request and response is huge.
* Reset search when collaborator dropdown closes.
* Stop creating tsv columns when PG_FULLTEXT_SEARCH is disabled.

### Refactors
* [Builder] Add Formula Generator to extract formulas for Elements. [#2063](https://gitlab.com/baserow/baserow/-/issues/2063)
* [Builder] Ensure the Element Panel's Dropdown and Input fields use the dense style. [#2705](https://gitlab.com/baserow/baserow/-/issues/2705)
* [Builder] Improve how Choice Element's values are auto-populated. [#2706](https://gitlab.com/baserow/baserow/-/issues/2706)
* Make unittests more resiliant to environment variables changes [#2801](https://gitlab.com/baserow/baserow/-/issues/2801)
* Refactor array filter mixins [#2802](https://gitlab.com/baserow/baserow/-/issues/2802)
* Don t recreate table column when updating a formula field if not needed [#2890](https://gitlab.com/baserow/baserow/-/issues/2890)
* Reschedule view index creation if table is already locked. [#2934](https://gitlab.com/baserow/baserow/-/issues/2934)
* [Builder] Improve UX for the Choice Element: auto-fill Values, reverse Name and Value positions, and update translations. [#2706](https://gitlab.com/baserow/baserow/-/issues/2706)
* [Builder] Remove zero downtime related field properties. Some fields can't be null anymore.
* Change title template suffix from `// Baserow` to `| Baserow`.
* Modify formulas to update values in correct dependency order instead of expanding each referenced formula for every field.

### Breaking API changes
* The `include` query parameter now excludes link row fields unless they are explicitly listed when listing rows. [#2903](https://gitlab.com/baserow/baserow/-/issues/2903)


## Released 1.26.1

### Bug fixes
* [Builder] Fix broken authentication with cookie generated with previous version


## Released 1.26.0

### New features
* Limit selection of link to table row to a view. [#1242](https://gitlab.com/baserow/baserow/-/issues/1242)
* [Builder] Improved application styling capabilities [#2388](https://gitlab.com/baserow/baserow/-/issues/2388)
* [Builder] More styles of the builder elements can be customized [#2388](https://gitlab.com/baserow/baserow/-/issues/2388)
* [Builder] Allow choice element options to be populated from formulas [#2489](https://gitlab.com/baserow/baserow/-/issues/2489)
* [Builder] Add support for controlling Element visibility via User Roles in the Element's Visibility Tab. [#2498](https://gitlab.com/baserow/baserow/-/issues/2498)
* [Builder] Added support for form elements within a repeat element. [#2636](https://gitlab.com/baserow/baserow/-/issues/2636)
* Add ability to delete row in calendar view [#2722](https://gitlab.com/baserow/baserow/-/issues/2722)

### Bug fixes
* Ensure that Context menus can be opened for input fields that are fully within the viewport. [#2013](https://gitlab.com/baserow/baserow/-/issues/2013)
* Generate file name for files uploaded by url where URL doesn't contain any path. [#2738](https://gitlab.com/baserow/baserow/-/issues/2738)
* When POST/PATCH operation on a row receives body other than a dict, HTTP 400 will be returned. [#2740](https://gitlab.com/baserow/baserow/-/issues/2740)
* Fix multiple usage of filename contains filter [#2746](https://gitlab.com/baserow/baserow/-/issues/2746)
* Show a notification of a 500 error in the frontend [#2754](https://gitlab.com/baserow/baserow/-/issues/2754)
* Date field now can be cleared when a row is edited as a form. [#2764](https://gitlab.com/baserow/baserow/-/issues/2764)
* Fix a bug causing the 'not_empty' view filter showing empty rows for link to table fields. [#2777](https://gitlab.com/baserow/baserow/-/issues/2777)
* [Builder] Resolved an error where data source filters and sortings wouldn't work properly when they were targeting a trashed Baserow field. [#2790](https://gitlab.com/baserow/baserow/-/issues/2790)
* Prevent last_login update if the last_login time diff is < 1 minute

### Refactors
* Refactor formInput, formTextarea, formGroup components [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* [Builder] Make Element tag's appearance more rounded. Change Publish app's Open Tab action to use the open-new-window icon. [#2705](https://gitlab.com/baserow/baserow/-/issues/2705)


## Released 1.25.2

### New features
* Show full name of relationships [#1751](https://gitlab.com/baserow/baserow/-/issues/1751)
* Add ability to delete row in kanban view [#2179](https://gitlab.com/baserow/baserow/-/issues/2179)
* Add Celery Flower [#2255](https://gitlab.com/baserow/baserow/-/issues/2255)
* Serve files from the backend to authorized users and/or with temporary links. [#2474](https://gitlab.com/baserow/baserow/-/issues/2474)
* improve dropdown element to allow multi selection [#2515](https://gitlab.com/baserow/baserow/-/issues/2515)
* [Builder] Rename dropdown element to choice element and allow to display element as dropdown/checkbox/radio [#2517](https://gitlab.com/baserow/baserow/-/issues/2517)
* [Builder] Add responsive behavior configuration for table element [#2523](https://gitlab.com/baserow/baserow/-/issues/2523)
* Allow syncing only a specific subset of templates [#2611](https://gitlab.com/baserow/baserow/-/issues/2611)
* Enable single level nesting of filter groups within existing groups [#2646](https://gitlab.com/baserow/baserow/-/issues/2646)
* Support file field as knowledge base for AI prompt [#2649](https://gitlab.com/baserow/baserow/-/issues/2649)

### Bug fixes
* Resolved an issue where moving elements stopped working from the element menu. [#2619](https://gitlab.com/baserow/baserow/-/issues/2619)
* Fix formula migration for elements inside a repeat element [#2648](https://gitlab.com/baserow/baserow/-/issues/2648)
* Resolved an issue where a refresh data source action being executed would cause duplicate entries to appear in a repeat element. [#2652](https://gitlab.com/baserow/baserow/-/issues/2652)
* [Builder] Resolved an issue where deleting a page when a table element in a different page relied on it would trigger an error during application duplication. [#2656](https://gitlab.com/baserow/baserow/-/issues/2656)
* Resolved an issue with duplicating a page containing a table with one or more columns of 'tags' type. [#2664](https://gitlab.com/baserow/baserow/-/issues/2664)
* Fix a bug in the formula language causing the filter condition to be ignored when aggregating values. [#2666](https://gitlab.com/baserow/baserow/-/issues/2666)
* [Builder] Resolved an issue which prevented the Open Page action from accessing the 'Previous action' provider. [#2707](https://gitlab.com/baserow/baserow/-/issues/2707)
* [Builder] Fix page parameter type to make possible to use them in linked row field of update row actions [#2708](https://gitlab.com/baserow/baserow/-/issues/2708)
* fix for UUIDFieldType that fails hard if filtered by ContainsViewFilterType and a non-UUID string [#2713](https://gitlab.com/baserow/baserow/-/issues/2713)
* Restored prior field form behavior: pressing enter when in field form elements won't spuriously open field description input anymore. [#2715](https://gitlab.com/baserow/baserow/-/issues/2715)
* Fixed bug with incorrect row ordering for editors and lower in views with group bys. [#2726](https://gitlab.com/baserow/baserow/-/issues/2726)
* Fix missing field validation error messages
* Fix periodic field update deadlock problem with tsv column update.
* Markdown content is generated on the server and can be indexed by search engine
* Resolved an issue where duplicating an image element pointing to a file would not work correctly.

### Refactors
* Display all elements in the 'add element' modal, and instead disable those which are unavailable. [#2607](https://gitlab.com/baserow/baserow/-/issues/2607)
* Remove vim and nano from dependencies [#2633](https://gitlab.com/baserow/baserow/-/issues/2633)
* Update posthog-js library to 1.136.2.


## Released 1.25.1

### Bug fixes
* Fix a bug causing the long/rich text field to close the text area when pressing shift+click. [#2612](https://gitlab.com/baserow/baserow/-/issues/2612)
* Fix issue when grouping by a single select field. [#2624](https://gitlab.com/baserow/baserow/-/issues/2624)
* Ensure Link elements work with Custom URL protocols like mailto, sms, or tel. [#2642](https://gitlab.com/baserow/baserow/-/issues/2642)
* Resolved an issue where links would not work properly in repeat elements within a published application. [#2653](https://gitlab.com/baserow/baserow/-/issues/2653)
* Fix empty user object when checking for onboarding.

### Breaking API changes
* In the Application Builder, when using a Custom URL in a Link element the Destination URL is no longer automatically prefixed with https://. Additionally, only these protocols are allowed in the Destination URL: ftp, ftps, ftpes, http, https, mailto, sftp, sms, and tel. [#2642](https://gitlab.com/baserow/baserow/-/issues/2642)


## Released 1.25.0

### New features
* Add support for table field name and table field Id for form prefills [#1576](https://gitlab.com/baserow/baserow/-/issues/1576)
* Add support for aggregations on public grid views [#1929](https://gitlab.com/baserow/baserow/-/issues/1929)
* Support for rich text field description [#2090](https://gitlab.com/baserow/baserow/-/issues/2090)
* Add aggregations support for last modified by and created by fields [#2114](https://gitlab.com/baserow/baserow/-/issues/2114)
* Add a new Application Builder action to refresh a Data Source in a page. [#2192](https://gitlab.com/baserow/baserow/-/issues/2192)
* Improved onboarding for new users. [#2212](https://gitlab.com/baserow/baserow/-/issues/2212)
* Add email verification options to user accounts [#2264](https://gitlab.com/baserow/baserow/-/issues/2264)
* Add support for `d h m` and `d h m s` duration formats. [#2284](https://gitlab.com/baserow/baserow/-/issues/2284)
* Add support in Application Builder to add a custom favicon. [#2301](https://gitlab.com/baserow/baserow/-/issues/2301)
* Links in table columns, and the "Open Page" action, will now support the same form configurations as the link element. [#2304](https://gitlab.com/baserow/baserow/-/issues/2304)
* Add a new Collection Field Type of Boolean in Application Builder. [#2359](https://gitlab.com/baserow/baserow/-/issues/2359)
* Templates are now compatible with application builder [#2387](https://gitlab.com/baserow/baserow/-/issues/2387)
* Send information to baserow.io if user agrees during onboarding. [#2412](https://gitlab.com/baserow/baserow/-/issues/2412)
* Add support for divisions,multiplications, and rollup formulas with the duration field. [#2416](https://gitlab.com/baserow/baserow/-/issues/2416)
* Add support for multi tag collection fields in Application Builder table element [#2480](https://gitlab.com/baserow/baserow/-/issues/2480)
* Introduced a new element type called 'Repeat'. Given a list datasource, will repeat its child elements n number of times for each result in the datasource. [#2485](https://gitlab.com/baserow/baserow/-/issues/2485)
* automatically populate fields in a table when selecting the data source [#2497](https://gitlab.com/baserow/baserow/-/issues/2497)
* Add a new "button" field to table element that can trigger actions based on current rows. [#2522](https://gitlab.com/baserow/baserow/-/issues/2522)
* Improve date filters by allowing multi step combinations. [#2537](https://gitlab.com/baserow/baserow/-/issues/2537)
* Prevent sending too many email verification emails [#2552](https://gitlab.com/baserow/baserow/-/issues/2552)
* Automatically login users upon email verification [#2557](https://gitlab.com/baserow/baserow/-/issues/2557)
* Allow instance admin to sign in even if email verification is set to enforced [#2558](https://gitlab.com/baserow/baserow/-/issues/2558)
* Add email verified confirmation page [#2559](https://gitlab.com/baserow/baserow/-/issues/2559)
* Support for negative duration field values. [#2567](https://gitlab.com/baserow/baserow/-/issues/2567)
  * duration field->text conversion values will match selected format
  * text->duration field conversion values should match selected format (otherwise the resulting value will be empty)
* The API now accepts a single integer or a CSV string or an array of strings as value for link row field type and an array of string or a CSV string for file field type. [#2570](https://gitlab.com/baserow/baserow/-/issues/2570)
* Automatically select the first element when the application builder page loads. [#2597](https://gitlab.com/baserow/baserow/-/issues/2597)
* Add warning about security in the visibility side panel. [#2627](https://gitlab.com/baserow/baserow/-/issues/2627)
* Allow generating a Baserow formula using AI
* Optionally limit the number of pending invites using the `BASEROW_MAX_PENDING_WORKSPACE_INVITES` environment variable.
* Show enterprise modal when clicking on disabled feature.
* Update Node.js version to 21.7.3

### Bug fixes
* Fix for duplicated select fields import from airtable [#1235](https://gitlab.com/baserow/baserow/-/issues/1235)
* Allow importing into a URL field. [#1437](https://gitlab.com/baserow/baserow/-/issues/1437)
* Fix formula recursion error in create/update row action when using multiple formule with the same data source [#2506](https://gitlab.com/baserow/baserow/-/issues/2506)
* Resolved an issue where the application builder sample pages getting created would result in an error. [#2512](https://gitlab.com/baserow/baserow/-/issues/2512)
* Fix broken filter when filtering a data source using the `Or` operation in the published version of a builder application [#2525](https://gitlab.com/baserow/baserow/-/issues/2525)
* Fix random loss of authentication in application builder [#2526](https://gitlab.com/baserow/baserow/-/issues/2526)
* fix sorts management in data source [#2527](https://gitlab.com/baserow/baserow/-/issues/2527)
* Table not visible in preview wasn't updated after login [#2534](https://gitlab.com/baserow/baserow/-/issues/2534)
* Resolved an edge-case where it'd be possible to publish an application to a deleted domain. [#2548](https://gitlab.com/baserow/baserow/-/issues/2548)
* Fixed a bug that prevented the possibility to add a link element to a column [#2565](https://gitlab.com/baserow/baserow/-/issues/2565)
* Show only visible roles in the team member creation/edit modal. [#2574](https://gitlab.com/baserow/baserow/-/issues/2574)
* Improved collection element (e.g. table, repeat) load more behaviour so that they are more resilient to slow/offline connections. [#2580](https://gitlab.com/baserow/baserow/-/issues/2580)
* Fix a bug when a user was trying to log in and their password was empty [#2596](https://gitlab.com/baserow/baserow/-/issues/2596)
* Resolved an issue where some application builder table element link-type fields were missing some data. [#2616](https://gitlab.com/baserow/baserow/-/issues/2616)
* Resolved an issue in the form container where resetting to initial values after submission wasn't working properly. [#2621](https://gitlab.com/baserow/baserow/-/issues/2621)
* Fix a bug causing the view to crash when grouping by a multiple select and a single select field. [#2624](https://gitlab.com/baserow/baserow/-/issues/2624)
* Update /api/user-files/upload-via-url/ endpoint to support urls ending with / [#2644](https://gitlab.com/baserow/baserow/-/issues/2644)
* Element visibility is now set to 'all' by default
* Fix form print capabilities.

### Refactors
* Automatically hide newly created fields on views that are shared publicly [#1585](https://gitlab.com/baserow/baserow/-/issues/1585)
* refactor buttons [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Python packaging updated, consistent python versions, makefile for automation [#2494](https://gitlab.com/baserow/baserow/-/issues/2494)
  * each backend tree is installable python package
  * makefile targets available for better automation
* notify about staff users being created with dev sh script [#2590](https://gitlab.com/baserow/baserow/-/issues/2590)
* Refactor the sync_templates command to use individual transactions for each template. [#2591](https://gitlab.com/baserow/baserow/-/issues/2591)
* Activate AWS storage if `AWS_STORAGE_BUCKET_NAME` instead of `AWS_ACCESS_KEY_ID`.
* Improved discoverability of paid features
* Update debian version in docker images to bookworm
* Update the list of unsupported field types for formula in our docs.

### Breaking API changes
* When sending a PATCH request to the api:applications:item endpoint, invalid payload keys will be ignored and will no longer cause an HTTP 400 error. [#2301](https://gitlab.com/baserow/baserow/-/issues/2301)


## Released 1.24.2

### Bug fixes
* Fix ownership when initializing PG15 database.


## Released 1.24.1

### New features
* Add the 'Clear' shortcut key for full-sized Mac keyboards. [#2198](https://gitlab.com/baserow/baserow/-/issues/2198)
* add input_type to InputTextElement to handle password type [#2446](https://gitlab.com/baserow/baserow/-/issues/2446)

### Bug fixes
* Fixes the Render deployment by enforcing http.
* Fix selecting role on database and table level.


## Released 1.24.0

### New features
* Make links in the URL field type clickable in the row edit modal. [#1072](https://gitlab.com/baserow/baserow/-/issues/1072)
* Display unavailable advanced/enterprise roles even if the user isn't on one of these plans [#1313](https://gitlab.com/baserow/baserow/-/issues/1313)
* Made email notifications clickable and link to related row. [#1881](https://gitlab.com/baserow/baserow/-/issues/1881)
* Introduce 'greater than or equal to' and 'lower than or equal to' filter types for number fields [#1988](https://gitlab.com/baserow/baserow/-/issues/1988)
* Add support for user mentions in the rich text field. [#2041](https://gitlab.com/baserow/baserow/-/issues/2041)
* Introduced is any of and is none of filters. [#2102](https://gitlab.com/baserow/baserow/-/issues/2102)
* Add keyboard shortcuts to interact with Application Builder elements: c (select child), p (select parent), arrow keys (select elements), arrow keys + alt/option (move elements). [#2198](https://gitlab.com/baserow/baserow/-/issues/2198)
* Add a new data provider that allows to use values from previous actions in formulas [#2224](https://gitlab.com/baserow/baserow/-/issues/2224)
* For Grid view, show field name on hover if it doesn't fit in the field width [#2236](https://gitlab.com/baserow/baserow/-/issues/2236)
* Allow optional co-branding in enterprise. [#2294](https://gitlab.com/baserow/baserow/-/issues/2294)
* Allow selecting entire array result in data explorer [#2347](https://gitlab.com/baserow/baserow/-/issues/2347)
* Allow to define visibility for elements in application builder [#2374](https://gitlab.com/baserow/baserow/-/issues/2374)
* Add logout action to application builder [#2390](https://gitlab.com/baserow/baserow/-/issues/2390)
* Add after login even for the authentication form [#2391](https://gitlab.com/baserow/baserow/-/issues/2391)
* Add links to the rich text field. [#2412](https://gitlab.com/baserow/baserow/-/issues/2412)
* Tweaked the application builder data source and events forms so that they occasionally use our smaller form input variant. [#2447](https://gitlab.com/baserow/baserow/-/issues/2447)
* Improved upon loading states for elements which can dispatch a workflow action. [#2449](https://gitlab.com/baserow/baserow/-/issues/2449)
* Allow overwriting generative ai settings on workspace level. [#2490](https://gitlab.com/baserow/baserow/-/issues/2490)
* Add && and || operators to the formula language [#2135](https://gitlab.com/baserow/baserow/-/issues/2135)
* Introduced a new AI field type

### Bug fixes
* Fixed copy and paste of unnamed rows for link row field [#1744](https://gitlab.com/baserow/baserow/-/issues/1744)
* Application builder integrations are now loaded with the application [#2156](https://gitlab.com/baserow/baserow/-/issues/2156)
* Fixed a bug that caused displacement of the filter type dropdown in survey mode forms. [#2400](https://gitlab.com/baserow/baserow/-/issues/2400)
* Allow selecting the value property for linked tables field. It also fixes the data schema icons for File fields" [#2402](https://gitlab.com/baserow/baserow/-/issues/2402)
* Resolved an issue where creating/updating a row in a workflow action would break if the field was read only. [#2408](https://gitlab.com/baserow/baserow/-/issues/2408)
* Improved formula input field reactivity [#2420](https://gitlab.com/baserow/baserow/-/issues/2420)
* Resolved an issue causing the rich text menus to malfunction in Safari. [#2428](https://gitlab.com/baserow/baserow/-/issues/2428)
* Resolved an issue where a list data source's row index would raise an error when used in the current_record data provider. [#2431](https://gitlab.com/baserow/baserow/-/issues/2431)
* Disable HTML support in the rich text field [#2450](https://gitlab.com/baserow/baserow/-/issues/2450)
* Fix  [#2464](https://gitlab.com/baserow/baserow/-/issues/2464)
* Resolved an error which was raised when an application was published with a misconfigured user source. [#2467](https://gitlab.com/baserow/baserow/-/issues/2467)
* Resolved an issue where updating a table element with an invalid data source would cause the backend to throw an unhandled error. [#2468](https://gitlab.com/baserow/baserow/-/issues/2468)
* ensure that the get row service type path importer receives no field it doesn t fail hard [#2473](https://gitlab.com/baserow/baserow/-/issues/2473)
* Using login form if you are already logged doesn't require to click twice on the button anymore [#2476](https://gitlab.com/baserow/baserow/-/issues/2476)
* Fix bug where cards were overlapping if the field name was too long. [#2478](https://gitlab.com/baserow/baserow/-/issues/2478)
* Resolved an issue preventing the import/export of workspaces containing a duration field. [#2507](https://gitlab.com/baserow/baserow/-/issues/2507)
* Restrict 'Manage members' context menu item to database applications only. [#2510](https://gitlab.com/baserow/baserow/-/issues/2510)
* Fix a bug preventing to trigger a test call for the `update_row` webhook event type. [#2511](https://gitlab.com/baserow/baserow/-/issues/2511)
* Collection fields are now deleted on table element update
* Dropdown opened low on the page opens upward now
* Fixed a memory leak in the all_models property key of the apps registry.
* Fix thread safety bug of the table get_model method. [#2421](https://gitlab.com/baserow/baserow/-/issues/2421)
* Restore dashboard performances when getting all applications

### Refactors
* Create base components for the AB [#2355](https://gitlab.com/baserow/baserow/-/issues/2355)
* Change application builder elements order

### Breaking API changes
* Made the application request serializers polymorphic.
  * Breaking change: when an application is created or updated via the API with an invalid `type` we will now return an `ERROR_APPLICATION_TYPE_DOES_NOT_EXIST` error code, rather than `ERROR_REQUEST_BODY_VALIDATION`.


## Released 1.23.2

### Bug fixes
* Fix thread safety bug of the table get_model method. [#2421](https://gitlab.com/baserow/baserow/-/issues/2421)


## Released 1.23.1

### New features
* Copy single value to all selected cells [#2238](https://gitlab.com/baserow/baserow/-/issues/2238)
* Added templates: Net Promoter score, Project Management, OOO Management, Agile Product Roadmap

### Bug fixes
* Resolved an issue causing duplicate notifications and improved handling of multiple WorkspaceInvitations for the same user. [#2350](https://gitlab.com/baserow/baserow/-/issues/2350)
* Tweaked the application builder Examples page table element columns. [#2382](https://gitlab.com/baserow/baserow/-/issues/2382)
* Fix port binding problem in the all in one image. [#2403](https://gitlab.com/baserow/baserow/-/issues/2403)
* ensure that the list rows service type path importer receives no row or field it doesn't fail. [#2411](https://gitlab.com/baserow/baserow/-/issues/2411)
* Fix error for invalid formulas in DropdownElement default value [#2414](https://gitlab.com/baserow/baserow/-/issues/2414)
* Resolved an issue where an application's user sources would try and list users when no table had been selected. [#2415](https://gitlab.com/baserow/baserow/-/issues/2415)
* Ensure the dispatch datasources endpoint handles missing pages properly. [#2417](https://gitlab.com/baserow/baserow/-/issues/2417)
* Fix error fro workflow actions with no loading indicator [#2418](https://gitlab.com/baserow/baserow/-/issues/2418)
* Resolved an issue with the update row workflow action throwing an error if an invalid row ID was provided. [#2419](https://gitlab.com/baserow/baserow/-/issues/2419)
* Improve page editor performances when using lots of input elements [#2420](https://gitlab.com/baserow/baserow/-/issues/2420)
* Delete group by if the field is changed to an incompatible type.
* Fixed public grid view failing is empty order_by parameter was provided.
* Show billable badge to billable roles.


## Released 1.23.0

### New features
* Introduced new password field type. [#2123](https://gitlab.com/baserow/baserow/-/issues/2123)
* Support ad hoc filtering in grid view for editor roles and lower [#2329](https://gitlab.com/baserow/baserow/-/issues/2329)
* Support ad hoc sorting in grid and gallery views [#2361](https://gitlab.com/baserow/baserow/-/issues/2361)
* Add ad hoc filtering support for editor and lower for gallery and kanban views [#2375](https://gitlab.com/baserow/baserow/-/issues/2375)
* Add rich text formatting and Markdown support to the long text field. [#622](https://gitlab.com/baserow/baserow/-/issues/622)
* Add the application builder

### Bug fixes
* Fix the number of workspaces in the admin dashboard. [#1195](https://gitlab.com/baserow/baserow/-/issues/1195)
* File import will now ignore spaces around text values [#2305](https://gitlab.com/baserow/baserow/-/issues/2305)
* Resolve the issue where table import options vanish upon interacting with the form that displays these options, disrupting the table import process. [#2326](https://gitlab.com/baserow/baserow/-/issues/2326)
* Fix bug blocking grid view access after creating a lookup to a duration field. [#2333](https://gitlab.com/baserow/baserow/-/issues/2333)
* Adjusted the title height in the row modal to accommodate long text. [#2334](https://gitlab.com/baserow/baserow/-/issues/2334)
* Fix a bug blocking users to add row color conditions if the primary field has no compatible filters. [#2341](https://gitlab.com/baserow/baserow/-/issues/2341)
* Use the correct `get_human_readable_value` when creating row related notifications. [#2345](https://gitlab.com/baserow/baserow/-/issues/2345)
* Return an empty body instead of a string with a HTTP 204 status code [#2348](https://gitlab.com/baserow/baserow/-/issues/2348)
* Prevent editor and lower roles from creating aggregations [#2369](https://gitlab.com/baserow/baserow/-/issues/2369)
* Sanitize filter values to remove nul characters [#2398](https://gitlab.com/baserow/baserow/-/issues/2398)
* Fix bug where the period field update can result in a deadlock when it has multiple dependencies.

### Refactors
* Optimize usage counters tasks to run only for updated tables. [#1297](https://gitlab.com/baserow/baserow/-/issues/1297)
* Refactored cache clearing logic to target only dynamic models, preserving the global cache for all models.
* Update axios and posthog-jw frontend libraries


## Released 1.22.3

### New features
* Clean up UserLogEntry table entries [#1792](https://gitlab.com/baserow/baserow/-/issues/1792)
* Add segmentControl UI component [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Add support to reference duration fields in the formula language. [#2190](https://gitlab.com/baserow/baserow/-/issues/2190)
* Add formats with days to the duration field. [#2217](https://gitlab.com/baserow/baserow/-/issues/2217)
* Allow custom public share URLs [#2292](https://gitlab.com/baserow/baserow/-/issues/2292)
* Use primary row value in email notifications instead of just row ids [#2293](https://gitlab.com/baserow/baserow/-/issues/2293)
* Show billable label only to workspace admins [#2295](https://gitlab.com/baserow/baserow/-/issues/2295)
* Added instructions on how to deploy Baserow to Railway. [#2308](https://gitlab.com/baserow/baserow/-/issues/2308)
* Update Django to 4.1.X [#761](https://gitlab.com/baserow/baserow/-/issues/761)
* Added instructions on how to deploy Baserow to Digital Ocean Apps. [#998](https://gitlab.com/baserow/baserow/-/issues/998)
* Prepared Cloudron, all-in-one Docker image, and Heroku for having multiple application builder domains.

### Bug fixes
* Keep space for title in the row edit modal [#1734](https://gitlab.com/baserow/baserow/-/issues/1734)
* Avoid dangling snapshots [#1793](https://gitlab.com/baserow/baserow/-/issues/1793)
* Remove trailing spaces from datetime_format formula [#2131](https://gitlab.com/baserow/baserow/-/issues/2131)
* Fix get_adjacent_row bug causing not returning the correct adjacent row in certain situations. [#2273](https://gitlab.com/baserow/baserow/-/issues/2273)
* Fixes for Render deployments after changes for their plans. [#2275](https://gitlab.com/baserow/baserow/-/issues/2275)
* Fixes bug where the context menu was displaced if there was a vertical scrollbar (e.g. form form). [#2286](https://gitlab.com/baserow/baserow/-/issues/2286)
* Fix higher_than and lower_than frontend view filters for formula fields. [#2289](https://gitlab.com/baserow/baserow/-/issues/2289)
* Nullify single select field for KanbanView if it's been trashed. [#711](https://gitlab.com/baserow/baserow/-/issues/711)
* Fix cannot read properties of undefined workspace when navigating to a table that you don't have access to.
* Fix bug where combined database and table level roles would not be respected when listing permissions.
* Introduce Airtable import remove invalid surrogates JSON loads fallback.
* Fixed a bug where the SENTRY_DSN env var was ignored.

### Refactors
* Redesign checkbox component [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Refactor avatar UI component [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* refactor badge component [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Change analytics blacklist to whitelist [#2204](https://gitlab.com/baserow/baserow/-/issues/2204)

### Breaking API changes
* New formulas returning a date_interval/duration are sent as number of seconds instead of a formatted string. [#2190](https://gitlab.com/baserow/baserow/-/issues/2190)


## Released 1.22.2

### New features
* Allow form view prefill of multiple link to table entries [#2024](https://gitlab.com/baserow/baserow/-/issues/2024)
* Show the button formula as a clickable button. [#2089](https://gitlab.com/baserow/baserow/-/issues/2089)
* Add group by support for the duration field type [#2191](https://gitlab.com/baserow/baserow/-/issues/2191)
* Implement Sentry integration (FE/BE) via environment variables. [#2205](https://gitlab.com/baserow/baserow/-/issues/2205)
* Allow string values for link row field and multi select [#2250](https://gitlab.com/baserow/baserow/-/issues/2250)

### Bug fixes
* Fixed bug where row was overwritten on update. It now only updates read-only data. [#1405](https://gitlab.com/baserow/baserow/-/issues/1405)
* Fixed bug where it was not possible to update a row that was still being created. [#1507](https://gitlab.com/baserow/baserow/-/issues/1507)
* Introduce en-x-icu collation for basic fields [#1603](https://gitlab.com/baserow/baserow/-/issues/1603)
* Fix bug when clicking browser's back button didn't close Row edit modal. [#2140](https://gitlab.com/baserow/baserow/-/issues/2140)
* Fix a bug that prevent s manually reordering rows if a filter is applied on a hidden field. [#2175](https://gitlab.com/baserow/baserow/-/issues/2175)
* Dont propagate ViewDoesNotExist in updating index task [#2202](https://gitlab.com/baserow/baserow/-/issues/2202)
* Return proper exception when share_id is invalid [#2203](https://gitlab.com/baserow/baserow/-/issues/2203)
* Fix bug where the `source` argument was passed to the child serializer when user_field_names=True. [#2268](https://gitlab.com/baserow/baserow/-/issues/2268)

### Refactors
* refactor pagination component [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Change cookie values stored for last remembered view ID to shorter ones. [#2105](https://gitlab.com/baserow/baserow/-/issues/2105)


## Released 1.22.1

### Bug fixes
* Fix bug causing Baserow to use empty jwt secret by default when running baserow from docker compose. [#2160](https://gitlab.com/baserow/baserow/-/issues/2160)
* Fixed incorrect handling of row moved warning.


## Released 1.22.0

### New features
* Add support for multiple select in the formula field. Add `has_option` formula to check if a multiple select field has a specific option. [#1363](https://gitlab.com/baserow/baserow/-/issues/1363)
* Group rows by field. [#143](https://gitlab.com/baserow/baserow/-/issues/143)
* Allow switching between personal and collaborative views. [#1449](https://gitlab.com/baserow/baserow/-/issues/1449)
* Added UUID field type. [#1463](https://gitlab.com/baserow/baserow/-/issues/1463)
* Allow choosing a checkbox input option for the multiple select field in the form view. [#1899](https://gitlab.com/baserow/baserow/-/issues/1899)
* Add chips UI component [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Redesign context and select menus [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Restyle input and textarea [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Restyle radio button [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Add Last Modified By field [#2042](https://gitlab.com/baserow/baserow/-/issues/2042)
* Send a notification on form submission to subscribed users. [#2054](https://gitlab.com/baserow/baserow/-/issues/2054)
* Allow to follow/unfollow comments on a specific row. [#2086](https://gitlab.com/baserow/baserow/-/issues/2086)
* Display 'available in premium version' message for non-premium users when switching view to Personal [#2087](https://gitlab.com/baserow/baserow/-/issues/2087)
* Add the duration field type. [#2088](https://gitlab.com/baserow/baserow/-/issues/2088)
* Add support for sorting Last Modified By fields [#2106](https://gitlab.com/baserow/baserow/-/issues/2106)
* Add support for search for last modified by field type [#2108](https://gitlab.com/baserow/baserow/-/issues/2108)
* Add is, is not, empty, not empty filters for last modified by field [#2109](https://gitlab.com/baserow/baserow/-/issues/2109)
* Immediate frontend rendering for changing Last modified by field values [#2113](https://gitlab.com/baserow/baserow/-/issues/2113)
* Add the created_by field type. [#624](https://gitlab.com/baserow/baserow/-/issues/624)
* Add autonumber field [#811](https://gitlab.com/baserow/baserow/-/issues/811)
* Allow choosing a radio input option for the single select field in the form view. [#813](https://gitlab.com/baserow/baserow/-/issues/813)
* Introduced `BASEROW_FRONTEND_SAME_SITE_COOKIE` environment variable to change the cookie sameSite value.
* New templates:
  * Beverage Sales Management
  * Car Comparison
  * ESG Management
  * Staff Development

### Bug fixes
* Fixed incorrect font in emails by introducing fallback. [#1947](https://gitlab.com/baserow/baserow/-/issues/1947)
* Fixes the deadlock errors that can occur when updating TSV cells. [#1984](https://gitlab.com/baserow/baserow/-/issues/1984)
* Fix shift arrow selection on grid view when primary key field option is not first [#1998](https://gitlab.com/baserow/baserow/-/issues/1998)
* Make date field responsive in Row dialog. [#2048](https://gitlab.com/baserow/baserow/-/issues/2048)
* Fixed a bug that prevented table duplication when a 'Link to Table' field is modified to link to a different table. [#2053](https://gitlab.com/baserow/baserow/-/issues/2053)
* Remove the 'App pitch planner' database from the 'Elementary School Management System' template. [#2060](https://gitlab.com/baserow/baserow/-/issues/2060)
* Fix a bug causing the 'Duplicate row' in the UI not showing values correctly for single and multiple select fields. [#2068](https://gitlab.com/baserow/baserow/-/issues/2068)
* Fix a bug preventing lookup fields to work properly with last modified fields. [#2081](https://gitlab.com/baserow/baserow/-/issues/2081)
* Fixed a bug causing the UI to freeze on clicking the already opened table link in sidebar. [#2082](https://gitlab.com/baserow/baserow/-/issues/2082)
* Fix filename inconsistency for downloaded files [#2096](https://gitlab.com/baserow/baserow/-/issues/2096)
* Disable incompatible filters in public views [#2116](https://gitlab.com/baserow/baserow/-/issues/2116)
* Fix values not being updated in row edit modal if the row is not in the buffer. [#2128](https://gitlab.com/baserow/baserow/-/issues/2128)
* Fix a bug causing comments not syncing in row edit modal on navigation. [#2144](https://gitlab.com/baserow/baserow/-/issues/2144)
* Fix bug causing the notification panel to crash with comment notifications lacking user sender [#2157](https://gitlab.com/baserow/baserow/-/issues/2157)
* Disable session recording in Posthog to prevent ReportingObserver error.
* Fix show paginated response of the APIListingView in the OpenAPI spec.
* Fixed undefined event when copying rows via multiple row context.
* Fix duplicate darker color in palette.
* Fix limit of the multiple selection in the web-frontend
* Resolve the postcss-loader warnings.
* Fix bug where commenters were not able to see row comments and change history.
* Suppress redirect error when selecting the database application.

### Refactors
* Alert and toast refactor [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Reduce the amount of data written from automatic field updates when possible. [#2021](https://gitlab.com/baserow/baserow/-/issues/2021)
* Pick a valid view from the available ones if a rowId is provided in the route params. [#2095](https://gitlab.com/baserow/baserow/-/issues/2095)
* Add the `workspace_id` and the `database_id` to webhook payload. [#2147](https://gitlab.com/baserow/baserow/-/issues/2147)
* Improved performance of the field dependency updating.
* Improved performance of the field serialized import export, resulting in fast duplication.


## Released 1.21.2

### Bug fixes
* Fixed redirect problem in the additional importer.


## Released 1.21.1

### Bug fixes
* Fixed an issue that prevented the kanban view from subscribing to row events.
* Prevent incorrect requests when opening row that has not yet been created.


## Released 1.21.0

### New features
* Add file field support to formula and lookup fields [#1012](https://gitlab.com/baserow/baserow/-/issues/1012)
* Make it possible to edit values in the row edit modal of a relationship [#1117](https://gitlab.com/baserow/baserow/-/issues/1117)
* Added condition groups for advanced row filtering using 'And' & 'Or' conjunctions. [#1271](https://gitlab.com/baserow/baserow/-/issues/1271)
* Add a new view filter for selecting rows whose file columns have less files than a given number [#1771](https://gitlab.com/baserow/baserow/-/issues/1771)
* Introduce new button styling [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Replace icons [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Restyle datepicker [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Restyle switch and checkbox components [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Restyle tabs component [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Add ability to subscribe to multiple pages via websockets [#2019](https://gitlab.com/baserow/baserow/-/issues/2019)
* Add row edit history [#2030](https://gitlab.com/baserow/baserow/-/issues/2030)
* Prevent CSV injection when exporting view to CSV format. [#2043](https://gitlab.com/baserow/baserow/-/issues/2043)
* Invalidate authentication tokens on password change. [#2044](https://gitlab.com/baserow/baserow/-/issues/2044)
* Expires the refresh token on log out. [#2045](https://gitlab.com/baserow/baserow/-/issues/2045)
* Enable linking to multiple link to table entries in form view [#810](https://gitlab.com/baserow/baserow/-/issues/810)
* Introduced endpoint to create a new user as admin.
* Reduced the number of queries when listing rows in a table that has many single/multiple select fields.
* Introduced space bar keyboard shortcut to open row edit modal in grid view. [#2030](https://gitlab.com/baserow/baserow/-/issues/2030)

### Bug fixes
* baserow round formula causing sql errors [#1595](https://gitlab.com/baserow/baserow/-/issues/1595)
* date interval addtion bug [#1742](https://gitlab.com/baserow/baserow/-/issues/1742)
* Prevent filters to be applied when the user open the row edit modal. [#1765](https://gitlab.com/baserow/baserow/-/issues/1765)
* the second formula function applied on a date field fails hard [#1812](https://gitlab.com/baserow/baserow/-/issues/1812)
* fix when_empty must be the same type error when working with url and email fields [#1880](https://gitlab.com/baserow/baserow/-/issues/1880)
* Fix rounded corners in edit row modal [#1950](https://gitlab.com/baserow/baserow/-/issues/1950)
* fix webhook url validation not being disabled when baserow_webhooks_allow_private_address true [#1959](https://gitlab.com/baserow/baserow/-/issues/1959)
* Fix a not working ctrl/cmd+f keyboard shortcut on pages that don't have a search box. [#1968](https://gitlab.com/baserow/baserow/-/issues/1968)
* Fix bug where the navigation history was wrong after last view. [#2006](https://gitlab.com/baserow/baserow/-/issues/2006)
* Fix a bug not clearing the notification store when the user logs out. [#2016](https://gitlab.com/baserow/baserow/-/issues/2016)
* Fix an issue with running Baserow in production mode [#2035](https://gitlab.com/baserow/baserow/-/issues/2035)
* Remove duplicate field options and fix remaining race in update_field_options [#725](https://gitlab.com/baserow/baserow/-/issues/725)
* Fix batch file request missing validation.
* Fix performance bug when N number `empty_count` view aggregation were added.
* Fix import serialized with missing select options error.
* Fix bug in the gallery view which resulted in the row edit modal not always having an update to do row.
* Reduced the number of `get_model` calls in the row endpoints.

### Refactors
* Replaced template icons with Iconoir.
* Replaced the logo with the new one.


## Released 1.20.2

### Bug fixes
* Fixed that the dropdowns in the filters context are being cut off [#1965](https://gitlab.com/baserow/baserow/-/issues/1965)
* Fix row ID being truncated in the grid view with 4 digit numbers in some browsers
* Respect the canKeyDown method when starting the multiple selection via keyboard shortcut


## Released 1.20.1

### New features
* Remember the last used view, per table, per user [#1273](https://gitlab.com/baserow/baserow/-/issues/1273)
* add split_part formula function [#1940](https://gitlab.com/baserow/baserow/-/issues/1940)
* introduce DATABASE_OPTIONS json string env var for setting additional database_options. [#1949](https://gitlab.com/baserow/baserow/-/issues/1949)

### Bug fixes
* fix pasting clearing multiple cells not showing results on a grid view with a hidden filtered [#1948](https://gitlab.com/baserow/baserow/-/issues/1948)
* Fixed performance problem with sorts because of an accidental query evaluation


## Released 1.20.0

### New features
* Add collapse button to hide the comments panel [#1599](https://gitlab.com/baserow/baserow/-/issues/1599)
* Added search functionality to Calendar View [#1634](https://gitlab.com/baserow/baserow/-/issues/1634)
* Added search parameter to Calendar view API [#1634](https://gitlab.com/baserow/baserow/-/issues/1634)
* Allow select options to optionally be positioned fixed. [#1659](https://gitlab.com/baserow/baserow/-/issues/1659)
* Enabled auto max height for views and workspaces context. [#1659](https://gitlab.com/baserow/baserow/-/issues/1659)
* Optionally automatically add a scrollbar to the context menu if it is outside of the viewport. [#1659](https://gitlab.com/baserow/baserow/-/issues/1659)
* Add `BASEROW_UNIQUE_ROW_VALUES_SIZE_LIMIT` environment variable to allow adjustment of the autodetection limit for multiselect options. [#1718](https://gitlab.com/baserow/baserow/-/issues/1718)
* Add 'Number is even and whole' view filter [#1783](https://gitlab.com/baserow/baserow/-/issues/1783)
* Added "Copy Row URL" link to row context menu [#1798](https://gitlab.com/baserow/baserow/-/issues/1798)
* Add new collaborator field option to notify any users when added as a collaborator in a cell. [#1807](https://gitlab.com/baserow/baserow/-/issues/1807)
* Add search shortcut for table views [#1815](https://gitlab.com/baserow/baserow/-/issues/1815)
* Add ability to select adjacent rows with Shift and arrow keys [#1847](https://gitlab.com/baserow/baserow/-/issues/1847)
* Add search shortcuts to other screens [#1870](https://gitlab.com/baserow/baserow/-/issues/1870)
* Send new notifications via email. [#1873](https://gitlab.com/baserow/baserow/-/issues/1873)
* Introduced color picker component. [#1889](https://gitlab.com/baserow/baserow/-/issues/1889)
* Introduce Workspace level audit log feature [#1901](https://gitlab.com/baserow/baserow/-/issues/1901)
* Introduce new border radius design [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Introduce new elevation design [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Update typography rules [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)
* Added support for `user_field_names` in the list rows endpoint's filtering mechanism. [#510](https://gitlab.com/baserow/baserow/-/issues/510)
* Add forumulas to encode complete and partial URIs. [#983](https://gitlab.com/baserow/baserow/-/issues/983)
* Implemented optional Posthog product analytics.

### Bug fixes
* Fix editable height when content is empty [#1858](https://gitlab.com/baserow/baserow/-/issues/1858)
* fix cells with massive amounts of causing full text search index updates to fail [#1869](https://gitlab.com/baserow/baserow/-/issues/1869)
* Fix allowing builders to create or edit lookup formulas to target fields in tables where they dont have access [#1883](https://gitlab.com/baserow/baserow/-/issues/1883)
* Ensure that the public grid view doesn't show a Delete Rows list item in its context. [#1907](https://gitlab.com/baserow/baserow/-/issues/1907)
* Fix prefill link to table fields display no longer working correctly. [#1913](https://gitlab.com/baserow/baserow/-/issues/1913)
* Fix submitting empty link_row value in form view. [#1914](https://gitlab.com/baserow/baserow/-/issues/1914)
* Fix not being able to delete a row with a link row cell pointing at a primary field with an empty multi select cell. [#1916](https://gitlab.com/baserow/baserow/-/issues/1916)
* two linked tables with publically shared views can cause bugs caused by prefetch caching fields [#1925](https://gitlab.com/baserow/baserow/-/issues/1925)
* prevent excessive number of sql statements being executed when using a deserialized model cache [#1926](https://gitlab.com/baserow/baserow/-/issues/1926)
* BooleanViewFilterType breaks comparing null values causing the frontend to crash. [#1927](https://gitlab.com/baserow/baserow/-/issues/1927)
* Fixed 'timezone for all collaborators' persistence in date fields. [#1928](https://gitlab.com/baserow/baserow/-/issues/1928)
* Fixed bug where duplicating a link/multi select/collaborator field with data resulted a duplicate field that couldn't have new values added until you tried a certain number of times. [#1931](https://gitlab.com/baserow/baserow/-/issues/1931)
* change backup_baserow to also batch up collaborator field m2m through tables as lock failures [#1933](https://gitlab.com/baserow/baserow/-/issues/1933)
* fix moving rows or updating link row fields in a tables with a lookup of a link row field [#1934](https://gitlab.com/baserow/baserow/-/issues/1934)
* Fix Airtable because `rawTables` key not found error.

### Refactors
* Don't use overwriting storage by default [#1878](https://gitlab.com/baserow/baserow/-/issues/1878)
* Remove the usage of 'TokenHandler.update_token_usage' method to improve performance [#1908](https://gitlab.com/baserow/baserow/-/issues/1908)
* Changed the font to Inter and use the new color palette. [#1918](https://gitlab.com/baserow/baserow/-/issues/1918)


## Released 1.19.1

### Bug fixes
* Do not run periodic field updates for trashed tables. [#1855](https://gitlab.com/baserow/baserow/-/issues/1855)
* Fix a link row field pointing a formula field using button link function breaking full text search for that table. [#1856](https://gitlab.com/baserow/baserow/-/issues/1856)
* Ensure default web frontend images nuxt command launches production version of image. [#1862](https://gitlab.com/baserow/baserow/-/issues/1862)
* fix web frontend not loading for ie and safari versions less than 16 4 [#1866](https://gitlab.com/baserow/baserow/-/issues/1866)


## Released 1.19.0

### New features
* After field updates, deletions and creations Baserow now automatically vacuums the table in a background task to improve performance and reduce table disk size. This can be disabled by setting the new env var BASEROW_AUTO_VACUUM=false. [#1706](https://gitlab.com/baserow/baserow/-/issues/1706)
* Rework Baserow row search to be much faster, work for all field types and instead search for words instead of exact matches including punctuation. Please note this new full text search mode can increase the disk space used by your Baserow tables upto 3x, to prevent this you can disable the new search and stick with the legacy slower but lower disk space usage search by setting the new env var BASEROW_USE_PG_FULLTEXT_SEARCH=false. [#1706](https://gitlab.com/baserow/baserow/-/issues/1706)
* Add new filter `is after days ago` for filtering records within a specified number of past days. [#1721](https://gitlab.com/baserow/baserow/-/issues/1721)
* Include the field name and ID in the grid view heading contexts. [#1726](https://gitlab.com/baserow/baserow/-/issues/1726)
* allow viewers commenters and editors to make personal views [#1737](https://gitlab.com/baserow/baserow/-/issues/1737)
* Mention other users in rows comments. [#1761](https://gitlab.com/baserow/baserow/-/issues/1761)
* Create a notification panel to show notifications [#1775](https://gitlab.com/baserow/baserow/-/issues/1775)
* Added the possibility to sort by lookup field and formula field resulting in a lookup for arrays of texts, numbers, booleans, and single selects [#1786](https://gitlab.com/baserow/baserow/-/issues/1786)
* Add options to edit and delete row comments. [#560](https://gitlab.com/baserow/baserow/-/issues/560)
* Allow line breaks in form view descriptions [#955](https://gitlab.com/baserow/baserow/-/issues/955)
* Introduced the yellow, purple, brown and pink colors.
* Added "Advertising Campaigns", "Company Advertising Campaigns", "Furniture, Fixtures, and Equipment Manager", "Household Chores", "Non-emergency Call Center", "Tourism Agency Manager", "Venture Capital Investments", "Copy Management", "Performance Reviews" and "Personal Finance Manager" template.

### Bug fixes
* Automatically add https protcol when it is missing from links [#1237](https://gitlab.com/baserow/baserow/-/issues/1237)
* Add prettier checks for scss files when linting. [#1796](https://gitlab.com/baserow/baserow/-/issues/1796)
* fix inviting member whilst on invite page causing crash [#1848](https://gitlab.com/baserow/baserow/-/issues/1848)
* Max and min can be used on date fields [#684](https://gitlab.com/baserow/baserow/-/issues/684)

### Refactors
* Move formula language into its own module [#1768](https://gitlab.com/baserow/baserow/-/issues/1768)
* Fix last modified not matching created on when making new rows [#1779](https://gitlab.com/baserow/baserow/-/issues/1779)
* Use nuxt runtimeConfig instead of nuxt-env module

### Breaking API changes
* Baserows default max per table field limit now defaults to 600 due to full text search and undo/redo needing to use the rest of the postgres 1600 column limit. This can be reverted using the new BASEROW_MAX_FIELD_LIMIT env var. If you want to have more than 600 fields we also recommend you turn off full text search as it needs an extra column per field to work, this can be done by setting BASEROW_USE_PG_FULLTEXT_SEARCH to false. [#1706](https://gitlab.com/baserow/baserow/-/issues/1706)
* Before when searching for a number say 1, it would match the row with id 1, 10, 11, 12 etc. Now it will only match rows with that exact id, so searching for 1 will match the row with id 1 and not the row with id 10 etc. [#1706](https://gitlab.com/baserow/baserow/-/issues/1706)
* By default in the UI search now uses full text mode which ignores punctuation and behaves differently than the previous exact matching. For now the API defaults to search_mode=compat, however in the coming months we will switch the API default to the new mode instead. [#1706](https://gitlab.com/baserow/baserow/-/issues/1706)
* Creating and updating row comments using the API endpoint '/api/row_comments' now requires a valid ProseMirror JSON document. See 'baserow.core.prosemirror.schema' for details. [#1761](https://gitlab.com/baserow/baserow/-/issues/1761)


## Released 1.18.0

### New features
* When copy-pasting, automatically create missing number of rows [#1252](https://gitlab.com/baserow/baserow/-/issues/1252)
* Add 2 date filters: `before or same date` and `after or same date`. [#1344](https://gitlab.com/baserow/baserow/-/issues/1344)
* Wrap migrate command in some sort of lock to prevent buggy concurrent migration runs in deployments with many Baserow backend services. [#1654](https://gitlab.com/baserow/baserow/-/issues/1654)
* add ability to copy and paste between different multi select option fields based on matching [#1750](https://gitlab.com/baserow/baserow/-/issues/1750)
* Introduced rollup field [#222](https://gitlab.com/baserow/baserow/-/issues/222)
* Introduced count field [#224](https://gitlab.com/baserow/baserow/-/issues/224)

### Bug fixes
* Fix redirect param being propagated [#1043](https://gitlab.com/baserow/baserow/-/issues/1043)
* Duplicating field with select options results in two fields sharing same underlying options. [#1735](https://gitlab.com/baserow/baserow/-/issues/1735)
* Fix drag and drop problem in Kanban view regarding inconsistent stack counts [#1738](https://gitlab.com/baserow/baserow/-/issues/1738)
* Fix browser freeze in older browsers when copying single cell [#1741](https://gitlab.com/baserow/baserow/-/issues/1741)
* Hide login buttons and login actions when afterSignupStepComponents are being displayed [#1747](https://gitlab.com/baserow/baserow/-/issues/1747)
* Fix issue where cachalot doesn't invalidate correctly `database_multipleselect_*` m2m tables. [#1772](https://gitlab.com/baserow/baserow/-/issues/1772)
* Made Airtable import compatible with signed files.

### Refactors
* Added datetime formats to be able to parse different datetimes (with momentjs strict mode enabled). [#1648](https://gitlab.com/baserow/baserow/-/issues/1648)


## Released 1.17.2

### New features
* Add new view filter type for dates 'is within x days', 'is within x weeks' and 'is within x months' [#1094](https://gitlab.com/baserow/baserow/-/issues/1094)
* Enable google and azure cloud storage backends for user file uploads and expose more S3 configuration env vars. [#1702](https://gitlab.com/baserow/baserow/-/issues/1702)

### Bug fixes
* Allow the use of longer Airtable share ids for import [#1132](https://gitlab.com/baserow/baserow/-/issues/1132)
* fix baserow internal connection errors resulting in server error shown when using ipv6 and [#1740](https://gitlab.com/baserow/baserow/-/issues/1740)

### Refactors
* Update vue-chartjs [#1683](https://gitlab.com/baserow/baserow/-/issues/1683)
* Turn cachalot off by default controlled by BASEROW_CACHALOT_ENABLED=true/false and ensure cachalot is in its own separate django cache which is cleared before migrations. [#1739](https://gitlab.com/baserow/baserow/-/issues/1739)


## Released 1.17.1

### Bug fixes
* Fix heroku error appearing when making a view sort. [#1736](https://gitlab.com/baserow/baserow/-/issues/1736)


## Released 1.17.0

### New features
* row create edit modal for calendar view [#1631](https://gitlab.com/baserow/baserow/-/issues/1631)
* public sharing for calendar view [#1637](https://gitlab.com/baserow/baserow/-/issues/1637)
* row coloring for calendar view [#1638](https://gitlab.com/baserow/baserow/-/issues/1638)
* Allow configuring Baserow to send emails using an implicit TLS connection and with custom SSL key files. [#1646](https://gitlab.com/baserow/baserow/-/issues/1646)
* Add a concurrent user requests rate limiter [#1673](https://gitlab.com/baserow/baserow/-/issues/1673)
* Update of backend dependencies [#1674](https://gitlab.com/baserow/baserow/-/issues/1674)
* use otel baggage to enhance every span with useful info [#1700](https://gitlab.com/baserow/baserow/-/issues/1700)
* Add the `datetime_format_tz` function to format dates in different timezones. [#1719](https://gitlab.com/baserow/baserow/-/issues/1719)
* support formula date fields in the calendar view [#1732](https://gitlab.com/baserow/baserow/-/issues/1732)
* Add a new admin health check page for seeing the status of your Baserow server. [#521](https://gitlab.com/baserow/baserow/-/issues/521)
* Add email tester to health check page for easily debugging Baserow email sending issues. [#521](https://gitlab.com/baserow/baserow/-/issues/521)
* Add new /api/_health/full/ JSON API healthcheck endpoint for admins only to run a full set of health checks against Baserow. [#521](https://gitlab.com/baserow/baserow/-/issues/521)
* Update all official Baserow images to now work on arm64 as well as amd64.  [#890](https://gitlab.com/baserow/baserow/-/issues/890)

### Bug fixes
* Ensure that enterprise role assignments are copied when an application and/or table are duplicated or snapshotted. [#1548](https://gitlab.com/baserow/baserow/-/issues/1548)
* fix slow loading of table with hundreds of views caused by serializer in list_views endpoint [#1684](https://gitlab.com/baserow/baserow/-/issues/1684)
* Fix enterprise migration being mentioned from core migration causing removal of enterprise app to break migrations. [#1696](https://gitlab.com/baserow/baserow/-/issues/1696)
* fix cors errors with aws s3 file download buttons in chromium based browsers [#1708](https://gitlab.com/baserow/baserow/-/issues/1708)
* otel_resource_attributes overwritten in all in one deploy preventing custom set attributes [#1711](https://gitlab.com/baserow/baserow/-/issues/1711)
* Fixes a bug where a wrong empty view is generated in some cases during the Airtable import.

### Refactors
* Bump frontend dependencies [#1675](https://gitlab.com/baserow/baserow/-/issues/1675)
* Lazy load nested table models when needed to improve `table.get_model` performances [#1695](https://gitlab.com/baserow/baserow/-/issues/1695)
* improve performance for has doesn t have filters [#1698](https://gitlab.com/baserow/baserow/-/issues/1698)
* Update frontend dependencies for plugin boilerplate [#1705](https://gitlab.com/baserow/baserow/-/issues/1705)
* Auto generate a database index per view based on sorts and add django-cachalot to speed up count() [#720](https://gitlab.com/baserow/baserow/-/issues/720)
* Changed repository URL to the one in the GitLab Baserow group
* reduce amount of queries when listing applications

### Breaking API changes
* Remove BASEROW_FULL_HEALTHCHECKS env var as private _health check endpoint which this env var affected has been simplified, depricated and replaced with the new /api/_health/full/ endpoint. [# ](https://gitlab.com/baserow/baserow/-/issues/ )
* Increased the snapshot permission requirements from Editor to Admin. [#1548](https://gitlab.com/baserow/baserow/-/issues/1548)
  * Creating a snapshot will now require an Admin role.
  * Restoring a snapshot will now require an Admin role.
  * Listing snapshots will now require an Admin role.
  * Deleting snapshots will now require an Admin role.
* Depricate private _health/ check endpoint and simplify the check it performs for security reasons.


## Released 1.16.1-rc1

### New features
* Add new env var BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT, which when set allows logging in using multiple different SSO providers to the same account [#1677](https://gitlab.com/baserow/baserow/-/issues/1677)


## Released 1.16.0

### New features
* Add multiple cells selection with shift+click [#1157](https://gitlab.com/baserow/baserow/-/issues/1157)
* Add calendar view [#140](https://gitlab.com/baserow/baserow/-/issues/140)
* Pre-fill name field after the linked table name [#1619](https://gitlab.com/baserow/baserow/-/issues/1619)

### Bug fixes
* Fix Updating formula field doesn't delete incompatible filters and sorts [#1608](https://gitlab.com/baserow/baserow/-/issues/1608)
* Fix date picker grid breaking on smaller zoom levels [#1640](https://gitlab.com/baserow/baserow/-/issues/1640)
* fix formula with now and field functions not always periodically refreshing [#1650](https://gitlab.com/baserow/baserow/-/issues/1650)
* Fix clicking on the download link of an image randomly opened the file instead. [#1652](https://gitlab.com/baserow/baserow/-/issues/1652)
* fix airtable importer crashing for rich text field containing user mention [#1660](https://gitlab.com/baserow/baserow/-/issues/1660)
* ensure personal views are available in the advanced baserow plan [#1663](https://gitlab.com/baserow/baserow/-/issues/1663)
* Fixed calendar styling [#1666](https://gitlab.com/baserow/baserow/-/issues/1666)
* Fix bug causing the frontend send wrong datetime values to the backend when using date/time pickers [#1667](https://gitlab.com/baserow/baserow/-/issues/1667)
* baserow realtime collaboration broken in heroku after channels upgrade [#1676](https://gitlab.com/baserow/baserow/-/issues/1676)
* Fix grid multiselect on small resolutions
* Fixed DRF Spectacular memory leak by caching the response and various warnings.
* Prevent validation error message to be displayed when adding a new field

### Refactors
* Globally renamed the concept of a 'group' to 'workspace'. [#1303](https://gitlab.com/baserow/baserow/-/issues/1303)
  * https://baserow.io/docs/apis%2Fdeprecations
* Renamed group to workspace in the frontend translations. [#1642](https://gitlab.com/baserow/baserow/-/issues/1642)


## Released 1.15.2

### Bug fixes
* Fix bug that prevented from decoding dates sent as prefilled values in form URLs [#1630](https://gitlab.com/baserow/baserow/-/issues/1630)
* Fix performance problem when checking token permissions


## Released 1.15.1

### Bug fixes
* Unregister the teams_in_group scope properly when navigating away from the teams settings page. [#1607](https://gitlab.com/baserow/baserow/-/issues/1607)
* fix forms with multiple select fields not being submitable [#1625](https://gitlab.com/baserow/baserow/-/issues/1625)
* Fix field creation when submitting with return/enter key


## Released 1.15.0

### New features
* Introduced a new command, `permanently_empty_database`, which will empty a database of all its tables. [#1090](https://gitlab.com/baserow/baserow/-/issues/1090)
* Improve create and edit field context [#1160](https://gitlab.com/baserow/baserow/-/issues/1160)
  * Set field context menu width to 400px
  * Open field type dropdown when field context menu is opened
  * Set field name after field type when empty
  * Increase field context menu dropdown height
* Allow closing file preview by clicking outside [#1167](https://gitlab.com/baserow/baserow/-/issues/1167)
* Added "Contains word" and "Doesn't contain word" filter for TextFieldType, LongTextFieldType, URLFieldType, EmailFieldType, SingleSelectFieldType, MultipleSelectFieldType and FormulaFieldType (text) fields. [#1236](https://gitlab.com/baserow/baserow/-/issues/1236)
* When right-clicking on the row add button in the grid view, you can now add multiple rows at a time. [#1249](https://gitlab.com/baserow/baserow/-/issues/1249)
* Add now() and today() formula with periodic updates [#1251](https://gitlab.com/baserow/baserow/-/issues/1251)
* Can add a row with textual values for single select, multiple select and link row field. [#1312](https://gitlab.com/baserow/baserow/-/issues/1312)
* Link row field can now be imported. [#1312](https://gitlab.com/baserow/baserow/-/issues/1312)
* Users can now create their own personal views. [#1448](https://gitlab.com/baserow/baserow/-/issues/1448)
* Make date fields timezone aware. [#1473](https://gitlab.com/baserow/baserow/-/issues/1473)
* Added missing actions for audit log. [#1500](https://gitlab.com/baserow/baserow/-/issues/1500)
* Show row and storage usage on premium admin group page. [#1513](https://gitlab.com/baserow/baserow/-/issues/1513)
* Add open telemetry exporters for logging, traces and metrics enabled using the BASEROW_ENABLE_OTEL env var. [#1518](https://gitlab.com/baserow/baserow/-/issues/1518)
* Add `is_nan` and `when_nan` formula functions [#1527](https://gitlab.com/baserow/baserow/-/issues/1527)
* Personal views improvements regarding premium. [#1532](https://gitlab.com/baserow/baserow/-/issues/1532)
* Add links in docs to new community maintained Baserow helm chart at https://artifacthub.io/packages/helm/christianknell/baserow. [#1549](https://gitlab.com/baserow/baserow/-/issues/1549)
* Add ability to create application builder [#1567](https://gitlab.com/baserow/baserow/-/issues/1567)
* Make commenter role free for advanced and enterprise. [#1596](https://gitlab.com/baserow/baserow/-/issues/1596)
* Ensure that e2e tests have staff users to work with on post_migrate. [#1614](https://gitlab.com/baserow/baserow/-/issues/1614)
* Add e2e tests. [#820](https://gitlab.com/baserow/baserow/-/issues/820)
* Added new templates for 1.15
  * Business Goal Tracker (OKRs)
  * Health Inspection Reports
  * Home Remodeling
  * SMB Business Plan

### Bug fixes
* Fix 500 error when fetching an aggregation that computes to `NaN` [#1054](https://gitlab.com/baserow/baserow/-/issues/1054)
* Improved the handling of taking a snapshot of, or duplicating, a database with many thousands of tables. [#1090](https://gitlab.com/baserow/baserow/-/issues/1090)
* Fixed API docs for creating and updating rows are missing for Multiple Select and Multiple Collaborator fields. [#1196](https://gitlab.com/baserow/baserow/-/issues/1196)
* Fix issue where you wouldn't get an error if you inserted whitespace only into a form text field [#1202](https://gitlab.com/baserow/baserow/-/issues/1202)
* Fixed memory leak when using our example `docker-compose` and a https URL in `BASEROW_CADDY_ADDRESSES` files caused by an incorrect Caddy healthcheck. [#1516](https://gitlab.com/baserow/baserow/-/issues/1516)
* Fix date field failing hard when trying to prefill an empty form value. [#1521](https://gitlab.com/baserow/baserow/-/issues/1521)
* Fix backspace stop responding due to double mixins. [#1523](https://gitlab.com/baserow/baserow/-/issues/1523)
* Single scrollbar for the personal and collaborative views. [#1531](https://gitlab.com/baserow/baserow/-/issues/1531)
* Fixed Brotli decoding issue where you sometimes cannot import from Airtable. [#1555](https://gitlab.com/baserow/baserow/-/issues/1555)
* disable silky_analyze_queries by default in developer env as it causes double data updates [#1591](https://gitlab.com/baserow/baserow/-/issues/1591)
* Fix stuck jobs when error occured while in pending state [#1615](https://gitlab.com/baserow/baserow/-/issues/1615)
* fix event loop is closed errors after channels upgrade [#1621](https://gitlab.com/baserow/baserow/-/issues/1621)
* Stop backend from failing hard during csv export if a character can't be encoded [#697](https://gitlab.com/baserow/baserow/-/issues/697)
* Fix being able to submit lookup field options without a field being selected [#941](https://gitlab.com/baserow/baserow/-/issues/941)
* Add missing `procps` system package to all-in-one docker image fixing `/baserow/supervisor/docker-postgres-setup.sh run` (#1512)[https://gitlab.com/baserow/baserow/-/issues/1512]
* Fix SimpleGridView graphical glitches
  * Fix grid footer when only a few colums are displayed
  * Add right border on grid last column
  * Fix SimpleGridView border glitch in import modal

### Refactors
* improve row before insert and move performance by refactoring the order to a fraction system [#1083](https://gitlab.com/baserow/baserow/-/issues/1083)
* Refactor date view filters to consider timezone when filtering results. [#1473](https://gitlab.com/baserow/baserow/-/issues/1473)
* Move enterprise imports out of core. [#1537](https://gitlab.com/baserow/baserow/-/issues/1537)
* Improve existing templates for 1.15
  * Benefit Show Manager
  * Business Expenses
  * Emergency Triage Log
  * Employee Directory
  * Team Check-ins
* Upgrade Django Channels to version 4 and bumped other dependencies

### Breaking API changes
* Remove BASEROW_COUNT_ROWS_ENABLED and BASEROW_GROUP_STORAGE_USAGE_ENABLED env vars and replace them with a new setting on the settings page. [#1513](https://gitlab.com/baserow/baserow/-/issues/1513)
* **Baserow formula breaking change** formula functions now automatically coerce null arguments to sensible blank defaults. `'some text' + null = 'some text'` instead of previously resulting in 'null' for example. See [community post](https://community.baserow.io/t/baserow-formula-breaking-change-introducing-null-values-and-automatic-coercion/2306) for more information. [#996](https://gitlab.com/baserow/baserow/-/issues/996)


## Released (2023-01-18_1.14.0)

### New features
* Add the "Audit Log" enterprise feature. Now admins can see every action that has been done in the instance. [#1152](https://gitlab.com/baserow/baserow/-/issues/1152)
* Add "has" and "has not" filters for Collaborators field. [#1204](https://gitlab.com/baserow/baserow/-/issues/1204)
* Pressing shift + enter in a selected cell of the grid view creates a new row. [#1208](https://gitlab.com/baserow/baserow/-/issues/1208)
* Select the primary field in the grid view after creating a new row. [#1217](https://gitlab.com/baserow/baserow/-/issues/1217)
* Added a new setting to the Admin Settings page to enable/disable global group creation. [#1311](https://gitlab.com/baserow/baserow/-/issues/1311)
* When your permissions change you now get notified in the frontend to reload your page [#1312](https://gitlab.com/baserow/baserow/-/issues/1312)
* Add various help icons to explain RBAC in the UI [#1318](https://gitlab.com/baserow/baserow/-/issues/1318)
* Pressing enter on a selected cell should select the cell below. [#1329](https://gitlab.com/baserow/baserow/-/issues/1329)
* Introduced a "select" and "deselect all" members button to the teams modal. [#1335](https://gitlab.com/baserow/baserow/-/issues/1335)
* Database and table ids are now hashed in websocket messages to not leak sensitive data [#1374](https://gitlab.com/baserow/baserow/-/issues/1374)
* Limit the amount of characters for messages supplied with group invitations to 250 [#1455](https://gitlab.com/baserow/baserow/-/issues/1455)
* Add Free label to free roles on role selector [#1504](https://gitlab.com/baserow/baserow/-/issues/1504)
* ./dev.sh now uses "docker compose" command if available.
* New templates:
  * Car Dealership Inventory
  * Car Dealership Services
  * Customer Research
  * Frequent Flyer Rewards
  * Grocery Planner

### Bug fixes
* Fixed bug where it was not possible to change `conditional_color` decorator provider color after reloading. [#1098](https://gitlab.com/baserow/baserow/-/issues/1098)
* Fixed issue during importing of serialized applications causing formula columns to have incorrect database column [#1220](https://gitlab.com/baserow/baserow/-/issues/1220)
* Fixed encoding issue where you couldn't import xml files with non-ascii characters [#1360](https://gitlab.com/baserow/baserow/-/issues/1360)
* Fixed upgrading a license from premium to enterprise results in an expired license. [#1403](https://gitlab.com/baserow/baserow/-/issues/1403)
* Fixed issue where 2 admins could lower each others permissions at the same time and lock each other out [#1443](https://gitlab.com/baserow/baserow/-/issues/1443)
* Replaced the "contains not" and "has not" English filters with "doesn't contain" and "doesn't have" respectively. [#1452](https://gitlab.com/baserow/baserow/-/issues/1452)
* Tweaked the curl examples in the API documentation so that they work properly in all $SHELLs. [#1462](https://gitlab.com/baserow/baserow/-/issues/1462)
* Fixed a typo in the docker-compose.no-caddy.yml so it works out of the box. [#1469](https://gitlab.com/baserow/baserow/-/issues/1469)
* Form validator shows the correct message when a field is required. [#1475](https://gitlab.com/baserow/baserow/-/issues/1475)
* Prevent errors after migrating and syncing RBAC roles by adding migration to rename NO_ROLE to NO_ACCESS [#1478](https://gitlab.com/baserow/baserow/-/issues/1478)
* Fixed bug preventing groups from being restored when RBAC was enabled [#1485](https://gitlab.com/baserow/baserow/-/issues/1485)
* Fixed issue where importing a database would immediately close the modal and not show progress [#1492](https://gitlab.com/baserow/baserow/-/issues/1492)
* Fixed HOURS_UNTIL_TRASH_PERMANENTLY_DELETED environment variable is not converted to int. [#1499](https://gitlab.com/baserow/baserow/-/issues/1499)
* Fixed Change Password dialog not visible. [#1501](https://gitlab.com/baserow/baserow/-/issues/1501)
* Resolved an issue in `delete_expired_users` so that it doesn't delete groups when admins are deactivated and not marked for deletion. [#1503](https://gitlab.com/baserow/baserow/-/issues/1503)

### Refactors
* Replaced deprecated `execCommand('copy')` with `clipboard API` for copy and paste. [#1392](https://gitlab.com/baserow/baserow/-/issues/1392)
* Introduce a single-parent hierarchy for models.
* Refactor paving the way for a future removal of the `ExportJob` system in favor of the `core/jobs` one.

### Breaking API changes
* Changed the return code from `HTTP_200_OK` to `HTTP_202_ACCEPTED` if a `POST` is submitted to `/api/snapshots/application/$ID/` to start the async job.


## Released (2022-12-22_1.13.3)

### New features
* Added more Maths formula functions. [#1183](https://gitlab.com/baserow/baserow/-/issues/1183)
* Add support for "Empty" and "Not Empty" filters for Collaborator field. [#1205](https://gitlab.com/baserow/baserow/-/issues/1205)
* Possibility to disable password authentication if another authentication provider is enabled. [#1317](https://gitlab.com/baserow/baserow/-/issues/1317)
* Users with roles higher than viewer on tables and databases now counted as paid users
on the enterprise plan including users who get those roles from a team. [#1322](https://gitlab.com/baserow/baserow/-/issues/1322)
* Add support for wildcard '*' in the FEATURE_FLAG env variable which enables all features.
* (Enterprise Preview Feature) Database and Table level RBAC with Teams are now available as a preview feature for enterprise users, Add 'RBAC' to the FEATURE_FLAG env and restart var to enable.
* The ordering APIs can now accept a partial list of ids to order only these ids.

### Bug fixes
* Use the correct `OperationType` to restore rows [#1389](https://gitlab.com/baserow/baserow/-/issues/1389)
* Fixed an issue where you would get an error if you accepted a group invitation with `NO_ACCESS` as you role [#1394](https://gitlab.com/baserow/baserow/-/issues/1394)
* Link/Lookup/Formula fields work again when restricting a users access to the related table [#1439](https://gitlab.com/baserow/baserow/-/issues/1439)
* Prevent zooming in when clicking on an input on mobile. [#722](https://gitlab.com/baserow/baserow/-/issues/722)

### Refactors
* Set a fixed width for `card_cover` thumbnails to have better-quality images. [#1278](https://gitlab.com/baserow/baserow/-/issues/1278)


## Released (2022-12-8_1.13.2)

### New features
* Add drag and drop zone for files to the row edit modal [#1161](https://gitlab.com/baserow/baserow/-/issues/1161)
* Allow creating a new option by pressing enter in the dropdown [#1169](https://gitlab.com/baserow/baserow/-/issues/1169)
* Added the teams functionality as an enterprise feature. [#1226](https://gitlab.com/baserow/baserow/-/issues/1226)
* Automatically enable/disable enterprise features upon activation/deactivation without needing a page refresh first. [#1306](https://gitlab.com/baserow/baserow/-/issues/1306)
* Don't require password verification when deleting user account. [#1401](https://gitlab.com/baserow/baserow/-/issues/1401)
* Improved grid view on smaller screens by not making the primary field sticky. [#690](https://gitlab.com/baserow/baserow/-/issues/690)
* New items automatically get a new name in the modal. [1166](https://gitlab.com/baserow/baserow/-/issues/1166)

### Bug fixes
* Fixed failing webhook call log creation when a table has more than one webhooks. [#1100](https://gitlab.com/baserow/baserow/-/issues/1100)
* Fixed bug where only one condition per field was working in form's views. [#1400](https://gitlab.com/baserow/baserow/-/issues/1400)
* Fixed the Heroku deployment template. [#1420](https://gitlab.com/baserow/baserow/-/issues/1420)
* Fix "ERR_REDIRECT" for authenticated users redirected to the dashboard from the signup page. [1125](https://gitlab.com/baserow/baserow/-/issues/1125)
* Fixed a problem of some specific error messages not being recognized by the web front-end.

### Refactors
* Refresh the JWT token when needed instead of periodically. [#1294](https://gitlab.com/baserow/baserow/-/issues/1294)
* Remove "// Baserow" from title on a publicly shared view if `show_logo` is set to false. [#1378](https://gitlab.com/baserow/baserow/-/issues/1378)


## Released (2022-11-22_1.13.1)

### New features
* Made it possible to optionally hide fields in a publicly shared form by providing the `hide_FIELD` query parameter. [#1096](https://gitlab.com/baserow/baserow/-/issues/1096)
* Calendar / date field picker: Highlight the current date and weekend [#1128](https://gitlab.com/baserow/baserow/-/issues/1128)
* OAuth 2 flows now support redirects to specific pages. [#1288](https://gitlab.com/baserow/baserow/-/issues/1288)
* Add support for language selection and group invitation tokens for OAuth 2 and SAML. [#1293](https://gitlab.com/baserow/baserow/-/issues/1293)
* Implemented the option to start direct support if the instance is on the enterprise plan.

### Bug fixes
* `permanently_delete_marked_trash` task no longer fails on permanently deleting a table before an associated rows batch. [#1266](https://gitlab.com/baserow/baserow/-/issues/1266)
* Fixed bug where "add filter" link was not clickable if the primary field has no compatible filter types. [#1302](https://gitlab.com/baserow/baserow/-/issues/1302)
* Fixed authenticated state changing before redirected to the login page when logging off. [#1328](https://gitlab.com/baserow/baserow/-/issues/1328)
* Fixed OAuth 2 flows for providers that don't provide user's name. Email will be used as a temporary placeholder so that an account can be created. [#1371](https://gitlab.com/baserow/baserow/-/issues/1371)
* Raise an exception when a user doesn't have a required feature on an endpoint
* Standardize the API documentation "token" references.

### Refactors
* Moved the Open Sans font to the static directory instead of a Google fonts dependency. [#1246](https://gitlab.com/baserow/baserow/-/issues/1246)
* Replace the CSS classes for SSO settings forms. [#1336](https://gitlab.com/baserow/baserow/-/issues/1336)
* Changed `TableGroupStorageUsageItemType.calculate_storage_usage` to use a PL/pgSQL function to speedup the storage usage calculation.


## Released (2022-11-02_1.13.0)

### New features
* Always allow the cover image of a gallery view to be accessible by a public view [#1113](https://gitlab.com/baserow/baserow/-/issues/1113)
* Added the ability to double click a grid field name so that quick edits can be made. [#1147](https://gitlab.com/baserow/baserow/-/issues/1147)
* Add an option to remove the Baserow logo from your public view. [#1203](https://gitlab.com/baserow/baserow/-/issues/1203)
* Added SAML protocol implementation for Single Sign On as an enterprise feature. [#1227](https://gitlab.com/baserow/baserow/-/issues/1227)
* Added OAuth2 support for Single Sign On with Google, Facebook, GitHub, and GitLab as preconfigured providers. Added general support for OpenID Connect. [#1254](https://gitlab.com/baserow/baserow/-/issues/1254)
* Added Zapier integration code. [#816](https://gitlab.com/baserow/baserow/-/issues/816)
* Background pending tasks like duplication and template_install are restored in a new frontend session if unfinished. [#885](https://gitlab.com/baserow/baserow/-/issues/885)
* Expose `read_only` in the list fields endpoint.
* Made it possible to add additional signup step via plugins.
* Made it possible to filter on the `created_on` and `updated_on` columns, even though
they're not exposed via fields.
* Upgraded docker containers base images from `debian:buster-slim` to the latest stable `debian:bullseye-slim`.
* Upgraded python version from `python-3.7.16` to `python-3.9.2`.

### Bug fixes
* Fixed slug rotation for GalleryView. [#1232](https://gitlab.com/baserow/baserow/-/issues/1232)
* Fixed bug where it was not possible to select text in a selected and editing cell in Chrome. [#1234](https://gitlab.com/baserow/baserow/-/issues/1234)
* Selecting text in models, contexts, form fields and grid view cells no longer unselects when releasing the mouse outside. [#1243](https://gitlab.com/baserow/baserow/-/issues/1243)
* Duplicating a table with a removed single select option value no longer results in an error. [#1263](https://gitlab.com/baserow/baserow/-/issues/1263)
* Fixed bug where the row metadata was not updated when receiving a realtime event.

### Refactors
* Replace members modal with a new settings page. [#1229](https://gitlab.com/baserow/baserow/-/issues/1229)
* Frontend now install templates as an async job in background instead of using a blocking call. [#885](https://gitlab.com/baserow/baserow/-/issues/885)
* Changed the add label of several buttons.

### Breaking API changes
* Changed error codes returned by the premium license API endpoints to replacing `PREMIUM_LICENSE` with `LICENSE`. [#1230](https://gitlab.com/baserow/baserow/-/issues/1230)
* The "token_auth" endpoint response and "user_data_updated" messages now have an "active_licenses" key instead of "premium" indicating what licenses the user has active. [#1230](https://gitlab.com/baserow/baserow/-/issues/1230)
* Changed the JWT library to fix a problem causing the refresh-tokens not working properly. [#787](https://gitlab.com/baserow/baserow/-/issues/787)
* List jobs endpoint "list_job" returns now an object with jobs instead of a list of jobs. [#885](https://gitlab.com/baserow/baserow/-/issues/885)


## Released (2022-09-20_1.12.1)

### New features
* Show database and table duplication progress in the left sidebar. [#1059](https://gitlab.com/baserow/baserow/-/issues/1059)
* Always allow the cover image of a gallery view to be accessible by a public view [#1113](https://gitlab.com/baserow/baserow/-/issues/1113)
* Add a rich preview while importing data to an existing table. [#1120](https://gitlab.com/baserow/baserow/-/issues/1120)
* Made it possible to share the Kanban view publicly. [#1146](https://gitlab.com/baserow/baserow/-/issues/1146)
* Added support for placeholders in form headings and fields. [#1168](https://gitlab.com/baserow/baserow/-/issues/1168)
* Added link, button, get_link_label and get_link_url formula functions. [#818](https://gitlab.com/baserow/baserow/-/issues/818)
* Add env vars for controlling which URLs and IPs webhooks are allowed to use. [#931](https://gitlab.com/baserow/baserow/-/issues/931)
* New templates:
  * Copy Management
  * Hiking Guide
  * New Hire Onboarding
  * Property Showings
  * QA Test Scripts
  * Risk Assessment and Management
  * Web App UAT
* Updated templates:
  * Benefit Show Manager
  * Car Hunt
  * Wedding Client Planner

### Bug fixes
* Fixed a bug that breaks the link row modal when a formula is referencing a single select field. [#1111](https://gitlab.com/baserow/baserow/-/issues/1111)
* Always allow the cover image of a gallery view to be accessible by a public view [#1113](https://gitlab.com/baserow/baserow/-/issues/1113)
* Fixed an issue where customers with malformed file extensions were unable to snapshot or duplicate properly [#1194](https://gitlab.com/baserow/baserow/-/issues/1194)
* Fixed Multiple Collaborators field renames. Now renaming the field won't recreate the field so that data is preserved.
* Plugins can now change any and all Django settings instead of just the ones set previously by Baserow.
* Static files collected from plugins will now be correctly served.
* The /admin url postfix will now be passed through to the backend API for plugins to use.

### Refactors
* Formulas which referenced other aggregate formulas now will work correctly. [#1081](https://gitlab.com/baserow/baserow/-/issues/1081)
* Improved file import UX for existing table. [#1120](https://gitlab.com/baserow/baserow/-/issues/1120)
* Used SimpleGrid component for SelectRowModal. [#1120](https://gitlab.com/baserow/baserow/-/issues/1120)


## Released (2022-09-07_1.12.0)

### New features
* Add cancel button to field update context [#1020](https://gitlab.com/baserow/baserow/-/issues/1020)
* Sort fields on row select modal by the order of the first view in the related table. [#1062](https://gitlab.com/baserow/baserow/-/issues/1062)
* Allow not creating a reversed relationship with the link row field. [#1063](https://gitlab.com/baserow/baserow/-/issues/1063)
* Allow creating new rows when selecting a related row [#1064](https://gitlab.com/baserow/baserow/-/issues/1064)
* Search automatically after 400ms when chosing a related field via the modal. [#1091](https://gitlab.com/baserow/baserow/-/issues/1091)
* Added Multiple Collaborators field type. [#1119](https://gitlab.com/baserow/baserow/-/issues/1119)
* Add API token authentication support to multipart and via-URL file uploads. [#255](https://gitlab.com/baserow/baserow/-/issues/255)
* Introduced a premium form survey style theme. [#524](https://gitlab.com/baserow/baserow/-/issues/524)
* Enable `file field` in `form` views. [#525](https://gitlab.com/baserow/baserow/-/issues/525)
* Force browser language when viewing a public view. [#834](https://gitlab.com/baserow/baserow/-/issues/834)
* Fields can now be duplicated with their cell values also. [#964](https://gitlab.com/baserow/baserow/-/issues/964)
* Add a tooltip to applications and tables in the left sidebar to show the full name. [#986](https://gitlab.com/baserow/baserow/-/issues/986)
* Add `isort` settings to sort python imports.
* Add navigation buttons to the `RowEditModal`.
* Add row url parameter to `gallery` and `kanban` view.
* Added missing success printouts to `count_rows` and `calculate_storage_usage` commands.
* `list_groups` endpoint now also returns the list of all group users for each group.
* New signals `user_updated`, `user_deleted`, `user_restored`, `user_permanently_deleted` were added to track user changes.
* Only allow relative urls in the in the original query parameter.

### Bug fixes
* Resolve an issue with uploading a file via a URL when it contains a querystring. [#1034](https://gitlab.com/baserow/baserow/-/issues/1034)
* Fixed a bug when importing Airtable base with a date field less than 1000. [#1046](https://gitlab.com/baserow/baserow/-/issues/1046)
* Add new filter types 'is after today' and 'is before today'. [#1093](https://gitlab.com/baserow/baserow/-/issues/1093)
* Fixed a bug that make the grid view crash when searching text and a formula field is referencing a singe-select field. [#1110](https://gitlab.com/baserow/baserow/-/issues/1110)
* Prefetch field options on views that are iterated over on field update realtime events [#1113](https://gitlab.com/baserow/baserow/-/issues/1113)
* Resolve circular dependency in `FieldWithFiltersAndSortsSerializer` [#1113](https://gitlab.com/baserow/baserow/-/issues/1113)
* Clearing cell values multi-selected from right to left with backspace shifts selection to the right and results in wrong deletion. [#1134](https://gitlab.com/baserow/baserow/-/issues/1134)
* Fixed a bug that prevent to use arrows keys in the grid view when a formula field is selected. [#1136](https://gitlab.com/baserow/baserow/-/issues/1136)
* "Link to table" field does not allow submitting empty values. [#1159](https://gitlab.com/baserow/baserow/-/issues/1159)
* Resolve an invalid URL in the "Backend URL mis-configuration detected" error message. [#967](https://gitlab.com/baserow/baserow/-/issues/967)
* Fix various misspellings. Contributed by [@Josh Soref](https://github.com/jsoref/) using [check-spelling.dev](https://check-spelling.dev/)
* Fixed broken call grouping when getting linked row names from server.
* Fixed bug where the "Create option" button was not visible for the single and multiple
select fields in the row edit modal.
* Fixed bug where the link row field lookup didn't work in combination with password
protected views.
* Fixed bug where the row coloring didn't work in combination with group level premium.
* Fixed horizontal scroll on Mac OSX.

### Refactors
* Fixed error when sharing a view publicly with sorts more than one multi-select field. [#1082](https://gitlab.com/baserow/baserow/-/issues/1082)
* Fix view and fields getting out of date on realtime updates. [#1112](https://gitlab.com/baserow/baserow/-/issues/1112)
* Fixed crash in gallery view with searching. [#1130](https://gitlab.com/baserow/baserow/-/issues/1130)
* Users can copy/paste images into a file field. [#367](https://gitlab.com/baserow/baserow/-/issues/367)
* Make it possible to copy/paste/import from/to text values for multi-select and file fields. [#913](https://gitlab.com/baserow/baserow/-/issues/913)

### Breaking API changes
* The date parsing takes the date format into account when parsing unless the format respect the ISO-8601 format. This will change the value for ambiguous dates like `02/03/2020`.
* The export format of file fields has changed for CSV files. The new format is `fileName1.ext (file1url),fileName2.ext (file2url), ...`.


## Released (2022-07-27_1.11.0)

### New features
* Replaced all custom alert code with `Alert` component [#1016](https://gitlab.com/baserow/baserow/-/issues/1016)
* Added a new "is months ago filter". [#1018](https://gitlab.com/baserow/baserow/-/issues/1018)
* Added a new "is years ago filter". [#1019](https://gitlab.com/baserow/baserow/-/issues/1019)
* Added public gallery view [#1057](https://gitlab.com/baserow/baserow/-/issues/1057)
* Made it possible to select the entire row via the row context menu. [#1061](https://gitlab.com/baserow/baserow/-/issues/1061)
* Show modal when the users clicks on a deactivated premium features. [#1066](https://gitlab.com/baserow/baserow/-/issues/1066)
* Introduced environment variable to disable Google docs file preview. [#1074](https://gitlab.com/baserow/baserow/-/issues/1074)
* Add ability to create and restore snapshots. [#141](https://gitlab.com/baserow/baserow/-/issues/141)
* Added option to use view's filters and sorting when listing rows. [#190](https://gitlab.com/baserow/baserow/-/issues/190)
* Made it possible to import data into an existing table. [#342](https://gitlab.com/baserow/baserow/-/issues/342)
* Add configs and docs for VSCode setup. [#854](https://gitlab.com/baserow/baserow/-/issues/854)
* Allow users to use row id in the form redirect URL. [#871](https://gitlab.com/baserow/baserow/-/issues/871)
* When viewing an expanded row switch to a unique URL which links to that row. [#938](https://gitlab.com/baserow/baserow/-/issues/938)
* Added a new `ClientUndoRedoActionGroupId` request header to bundle multiple actions in a single API call. [#951](https://gitlab.com/baserow/baserow/-/issues/951)
* Added `in this week` filter [#954](https://gitlab.com/baserow/baserow/-/issues/954)
* Applications can now be duplicated. [#960](https://gitlab.com/baserow/baserow/-/issues/960)
* Tables can now be duplicated. [#961](https://gitlab.com/baserow/baserow/-/issues/961)
* Conditionally show form fields.
* Fixed bug with 404 middleware returning different 404 error messages based on the endpoint.
* New templates:
  * Benefit Show Manager
  * Business Expenses
  * Emergency Triage Log
  * Employee Directory
  * Growth Experiments
  * Moving Company Manager
  * Online Freelancer Management
  * Personal Finance Manager
  * User Feedback
  * Workshops and Trainings
* Show badge when the user has account level premium.
* Updated templates:
  * Company Blog Management
  * Student Planner
  * Applicant Tracker
  * Book Catalog
  * Bucket List
  * Car Maintenance Log
  * Company Asset Tracker
  * Email Marketing Campaigns
  * Holiday Shopping
  * Recipe Book
  * Wedding Planning

### Bug fixes
* Disable table import field type guessing and instead always import as text fields. [#1050](https://gitlab.com/baserow/baserow/-/issues/1050)
* Add better error handling to row count job. [#1051](https://gitlab.com/baserow/baserow/-/issues/1051)
* Upgrade the images provided in our example docker-compose files to be the latest and most secure. [#1056](https://gitlab.com/baserow/baserow/-/issues/1056)
* Fix the perm delete trash cleanup job failing for self linking tables. [#1075](https://gitlab.com/baserow/baserow/-/issues/1075)
* Fixed changing field type to unsupported form view bug. [#1078](https://gitlab.com/baserow/baserow/-/issues/1078)
* Fix backspace and delete keys breaking after selecting a formula text cell. [#1085](https://gitlab.com/baserow/baserow/-/issues/1085)
* Fix some rare errors when combining the if and divide formula functions. [#1086](https://gitlab.com/baserow/baserow/-/issues/1086)
* Don't allow invalid aggregate formulas from being created causing errors when inserting rows. [#1089](https://gitlab.com/baserow/baserow/-/issues/1089)
* Ensure the latest error is always shown when clicking the formula refresh options link. [#1092](https://gitlab.com/baserow/baserow/-/issues/1092)
* Display round and trunc functions in the formula edit modal, rename int to trunc and make these functions handle weird inputs better. [#1095](https://gitlab.com/baserow/baserow/-/issues/1095)
* Fixed duplicating view with that depends on select options mapping. [#1104](https://gitlab.com/baserow/baserow/-/issues/1104)
* Fixed problem causing kanban view duplication to fail silently. [#1109](https://gitlab.com/baserow/baserow/-/issues/1109)
* Fixed problem when new webhooks would be sent twice with both old and new payload.

### Breaking API changes
* API endpoint `/database/views/grid/${viewSlug}/public/info/` has been replaced by `/database/views/${viewSlug}/public/info/` [#1057](https://gitlab.com/baserow/baserow/-/issues/1057)
* Removed `primary` from all `components`and `stores` where it isn't absolutely required. [#1057](https://gitlab.com/baserow/baserow/-/issues/1057)
* Fix not being able to paste multiple cells when a formula field of array or single select type was in an error state. [#1084](https://gitlab.com/baserow/baserow/-/issues/1084)
* Concurrent field updates will now respond with a 409 instead of blocking until the previous update finished, set the env var BASEROW_WAIT_INSTEAD_OF_409_CONFLICT_ERROR to revert to the old behaviour. [#1097](https://gitlab.com/baserow/baserow/-/issues/1097)
* API endpoints `undo` and `redo` now returns a list of actions undone/redone instead of a single action.
* **breaking change** Webhooks `row.created`, `row.updated` and `row.deleted` are
replaced with `rows.created`, `rows.updated` and `rows.deleted`, containing multiple
changed rows at once. Already created webhooks will still be called, but the received
body will contain only the first changed row instead of all rows. It is highly
recommended to convert all webhooks to the new types.


## Released (2022-07-05_1.10.2)

### New features
* Made the styling of the dashboard cleaner and more efficient. [#1023](https://gitlab.com/baserow/baserow/-/issues/1023)
* Redirect to signup instead of the login page if there are no admin users. [#1035](https://gitlab.com/baserow/baserow/-/issues/1035)
* Add startup check ensuring BASEROW_PUBLIC_URL and related variables are correct. [#1041](https://gitlab.com/baserow/baserow/-/issues/1041)
* Link to table field can now link rows in the same table. [#798](https://gitlab.com/baserow/baserow/-/issues/798)
* Added prefill query parameters for forms. [#852](https://gitlab.com/baserow/baserow/-/issues/852)
* Add support for horizontal scrolling in grid views pressing Shift + mouse-wheel. [#867](https://gitlab.com/baserow/baserow/-/issues/867)
* Added possibility to delete own user account [#880](https://gitlab.com/baserow/baserow/-/issues/880)
* Added formula round and int functions. [#891](https://gitlab.com/baserow/baserow/-/issues/891)
* Views can be duplicated. [#962](https://gitlab.com/baserow/baserow/-/issues/962)
* Add basic field duplication. [#964](https://gitlab.com/baserow/baserow/-/issues/964)
* Add the ability to disable the model cache with the new BASEROW_DISABLE_MODEL_CACHE env variable.
* Added API exception registry that allows plugins to provide custom exception mappings for the REST API.
* Added Link Row contains filter. [874](https://gitlab.com/baserow/baserow/-/issues/874)
* Added multi-cell clearing via backspace key (delete on Mac).
* Added new `before_group_deleted` signal that is called just before a group would end up in the trash.
* Added new `group_user_added` signal that is called when an user accept an invitation to join a group.
* Allow to import more than 15Mb. [949](ttps://gitlab.com/baserow/baserow/-/issues/949)
* `./dev.sh all_in_one_dev` now starts a hot reloading dev mode using the all-in-one image.
* Made it clearer that you're navigating to baserow.io when clicking the "Get a license"
button.
* Made it possible to extend the app layout.
* Made it possible to extend the register page.

### Bug fixes
* Fix regex_replace formula function allowing invalid types as params. [#1024](https://gitlab.com/baserow/baserow/-/issues/1024)
* Fix newly imported templates missing field dependencies for some link row fields. [#1025](https://gitlab.com/baserow/baserow/-/issues/1025)
* Fix converting a link row not updating dependants on the reverse side. [#1026](https://gitlab.com/baserow/baserow/-/issues/1026)
* Fix lookup field conversions deleting all of its old field dependencies. [#1036](https://gitlab.com/baserow/baserow/-/issues/1036)
* Fix refresh formula options button always being shown initially. [#1037](https://gitlab.com/baserow/baserow/-/issues/1037)
* Fix views becoming inaccessible due to race condition when invalidating model cache. [#1040](https://gitlab.com/baserow/baserow/-/issues/1040)
* Fix get_human_readable_value crashing for some formula types. [#1042](https://gitlab.com/baserow/baserow/-/issues/1042)
* Upload modal no longer closes when removing a file. [#569](https://gitlab.com/baserow/baserow/-/issues/569)
* Fix rare formula bug with multiple different formulas and view filters in one table. [#801](https://gitlab.com/baserow/baserow/-/issues/801)
* Added FormulaField to the options for the primary field. [#859](https://gitlab.com/baserow/baserow/-/issues/859)
* Treat null values as zeros for numeric formulas. [#886](https://gitlab.com/baserow/baserow/-/issues/886)
* Fix formula bug caused when looking up date intervals. [#924](https://gitlab.com/baserow/baserow/-/issues/924)
* Fix formula bugs caused by unsupported generation of BC dates. [#952](https://gitlab.com/baserow/baserow/-/issues/952)
* Fixed URL fields not being available in lookup fields. [#984](https://gitlab.com/baserow/baserow/-/issues/984)
* Add debugging commands/options for inspecting tables and updating formulas.
* API returns a nicer error if URL trailing slash is missing. [798](https://gitlab.com/baserow/baserow/-/issues/798)
* Fix dependant fields not being updated if the other side of a link row field changed. [918](https://gitlab.com/baserow/baserow/-/issues/918)
* Fix errors when using row_id formula function with left/right functions.
* Fix import form that gets stuck in a spinning state when it hits an error.
* Fix nested aggregate formulas not calculating results or causing errors. [683](https://gitlab.com/baserow/baserow/-/issues/683)


## Released (2022-06-09_1.10.1)

### New features
* Added a dropdown to the grid view that allows you to
select the type of row identifier displayed next to a row (`Count`or `Row Identifier`).
* Added an admin setting to disable the ability to reset a users password.
* Added BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION environment variable and now
do the sync_templates task in the background after migration to massively speedup
first time Baserow startup speed.
* Added multi-row delete.
* Added row coloring for Kanban and Gallery views
* Added the ability to use commas as separators in number fields
* **breaking change** The API endpoint `/api/templates/install/<group_id>/<template_id>/`
is now a POST request instead of GET.
* Deprecate the SYNC_TEMPLATES_ON_STARTUP environment variable and no longer call the
sync_templates command on startup in the docker images.
* Duplicate row.
* Fix a bug in public grid views that prevented expanding long-text cells.
* Fix deadlocks and performance problems caused by un-needed accidental row locks.
* Fix formula bug caused when arguments of `when_empty` have different types.
* Fixed bad request displayed with webhook endpoints that redirects
* Fixed CSV import adding an extra row with field names if the no headers option is selected.
* Formulas of type text now use textarea to show the cell value.
* Make fields sortable in row create/edit modal.
* Plugins can now include their own menu or other template in the main menu sidebar.
* Shift+Enter on grid view exit from editing mode for long text field
* Shift+Enter on grid view go to field below


## Released (2022-10-05_1.10.0)

### New features
* Add loading bar when syncing templates to make it obvious Baserow is still loading.
* Added 0.0.0.0 and 127.0.0.1 as ALLOWED_HOSTS for connecting to the Baserow backend
* Added a new BASEROW_EXTRA_ALLOWED_HOSTS optional comma separated environment variable
for configuring ALLOWED_HOSTS.
* Added batch create/update/delete rows endpoints. These endpoints make it possible to
modify multiple rows at once. Currently, row created, row updated, and row deleted
webhooks are not triggered when using these endpoints.
* Added group context menu to sidebar.
* Added `is days ago` filter to date field.
* Added multi-cell pasting.
* Added new endpoint to get all configured aggregations for a grid view
* Added new environment variable BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB
* Added password protection for publicly shared grids and forms.
* Added select option suggestions when converting to a select field.
* Added Spanish and Italian languages.
* Added support in dev.sh for KDE's Konsole terminal emulator.
* Added undo/redo.
* Allow the setting of max request page size via environment variable.
* Boolean field converts the word `checked` to `True` value.
* **breaking change** The API endpoint `/api/database/formula/<field_id>/type/` now requires
`table_id` instead of `field_id`, and also `name` in the request body.
* Cache aggregation values to improve performances
* Dropdown can now be focused with tab key
* Fix aggregation not updated on filter update
* Fix formula autocomplete for fields with multiple quotes
* Fix slowdown in large Baserow instances as the generated model cache got large.
* Fixed a bug for some number filters that causes all rows to be returned when text is entered.
* Fixed a bug that made it possible to delete created on/modified by fields on the web frontend.
* Fixed a bug that truncated characters for email in the sidebar
* Fixed a bug that would sometimes cancel multi-cell selection.
* Fixed a bug where making a multiple cell selection starting from an
empty `link_row` or `formula` field was not possible in Firefox.
* Fixed a bug where the backend would fail hard updating token permissions for deleted tables.
* Fixed a problem where a form view with link row fields sends duplicate lookup requests.
* Fixed Airtable import bug where the import would fail if a row is empty.
* Fixed bug preventing file uploads via an url for self-hosters
* Fixed bug where a cell value was not reverted when the request to the backend fails.
* Fixed bug where old values are missing in the update trigger of the webhook.
* Fixed bug where the arrow keys of a selected cell didn't work when they were not
rendered.
* Fixed bug where the link row field `link_row_relation_id` could fail when two
simultaneous requests are made.
* Fixed DONT_UPDATE_FORMULAS_AFTER_MIGRATION env var not working correctly.
* Fixed invalid `first_name` validation in the account form modal.
* Fixed occasional UnpicklingError error when getting a value from the model cache.
* Fixed plugin boilerplate guide.
* Fixed row coloring bug when the table doesn't have any single select field.
* Fixed the reactivity of the row values of newly created fields in some cases.
* Fixed the unchecked percent aggregation calculation
* Fixed translations in emails sent by Baserow.
* Fixed webhook test call failing when request body is empty.
* Improved backup_baserow splitting multiselect through tables in separate batches.
* Increased the max decimal places of a number field to 10.
* Introduced read only lookup of foreign row by clicking on a link row relationship in
the grid view row modal.
* Made it possible to impersonate another user as premium admin.
* Made views trashable.
* New templates:
  * Brand Assets Manager
  * Business Conference
  * Car Hunt
  * Company Blog Management
  * Event Staffing
  * Hotel Bookings
  * Nonprofit Grant Tracker
  * Performance Reviews
  * Product Roadmap
  * Public Library Inventory
  * Remote Team Hub
  * Product Roadmap
  * Hotel Bookings
* Pin backend python dependencies using pip-tools.
* **Premium** Added row coloring.
* Prevent the Airtable import from failing hard when an invalid date is provided.
* Raise Airtable import task error and fixed a couple of minor import bugs.
* Scroll to the first error message if the form submission fail
* Select new view immediately after creation.
* Shared public forms now don't allow creating new options
for single and multiple select fields.
* Stopped the generated model cache clear operation also deleting all other redis keys.
* The standalone `baserow/backend` image when used to run a celery service now defaults
to running celery with the same number of processes as the number of available cores.
* Updated templates:
  * Book writing guide
  * Bucket List
  * Call Center Log
  * Company Asset Tracker
  * Email Marketing Campaigns
  * Home Inventory
  * House Search
  * Job Search
  * Nonprofit Organization Management
  * Personal Task Manager
  * Political Campaign Contributions
  * Project Tracker
  * Recipe Book
  * Restaurant Management
  * Single Trip Planner
  * Software Application Bug Tracker
  * Student Planner
  * Teacher Lesson Plans
  * Team Check-ins
  * University Admissions Management
  * Wedding Client Planner
* Upgraded node runtime to v16.14.0
* When the BASEROW_AMOUNT_OF_WORKERS env variable is set to blank, the amount of worker
processes defaults to the number of available cores.


## Released (2022-10-05_1.10.0)

### New features
* Add loading bar when syncing templates to make it obvious Baserow is still loading.
* Added 0.0.0.0 and 127.0.0.1 as ALLOWED_HOSTS for connecting to the Baserow backend
* Added a new BASEROW_EXTRA_ALLOWED_HOSTS optional comma separated environment variable
for configuring ALLOWED_HOSTS.
* Added batch create/update/delete rows endpoints. These endpoints make it possible to
modify multiple rows at once. Currently, row created, row updated, and row deleted
webhooks are not triggered when using these endpoints.
* Added group context menu to sidebar.
* Added `is days ago` filter to date field.
* Added multi-cell pasting.
* Added new endpoint to get all configured aggregations for a grid view
* Added new environment variable BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB
* Added password protection for publicly shared grids and forms.
* Added select option suggestions when converting to a select field.
* Added Spanish and Italian languages.
* Added support in dev.sh for KDE's Konsole terminal emulator.
* Added undo/redo.
* Allow the setting of max request page size via environment variable.
* Boolean field converts the word `checked` to `True` value.
* **breaking change** The API endpoint `/api/database/formula/<field_id>/type/` now requires
`table_id` instead of `field_id`, and also `name` in the request body.
* Cache aggregation values to improve performances
* Dropdown can now be focused with tab key
* Fix aggregation not updated on filter update
* Fix formula autocomplete for fields with multiple quotes
* Fix slowdown in large Baserow instances as the generated model cache got large.
* Fixed a bug for some number filters that causes all rows to be returned when text is entered.
* Fixed a bug that made it possible to delete created on/modified by fields on the web frontend.
* Fixed a bug that truncated characters for email in the sidebar
* Fixed a bug that would sometimes cancel multi-cell selection.
* Fixed a bug where making a multiple cell selection starting from an
empty `link_row` or `formula` field was not possible in Firefox.
* Fixed a bug where the backend would fail hard updating token permissions for deleted tables.
* Fixed a problem where a form view with link row fields sends duplicate lookup requests.
* Fixed Airtable import bug where the import would fail if a row is empty.
* Fixed bug preventing file uploads via an url for self-hosters
* Fixed bug where a cell value was not reverted when the request to the backend fails.
* Fixed bug where old values are missing in the update trigger of the webhook.
* Fixed bug where the arrow keys of a selected cell didn't work when they were not
rendered.
* Fixed bug where the link row field `link_row_relation_id` could fail when two
simultaneous requests are made.
* Fixed DONT_UPDATE_FORMULAS_AFTER_MIGRATION env var not working correctly.
* Fixed invalid `first_name` validation in the account form modal.
* Fixed occasional UnpicklingError error when getting a value from the model cache.
* Fixed plugin boilerplate guide.
* Fixed row coloring bug when the table doesn't have any single select field.
* Fixed the reactivity of the row values of newly created fields in some cases.
* Fixed the unchecked percent aggregation calculation
* Fixed translations in emails sent by Baserow.
* Fixed webhook test call failing when request body is empty.
* Improved backup_baserow splitting multiselect through tables in separate batches.
* Increased the max decimal places of a number field to 10.
* Introduced read only lookup of foreign row by clicking on a link row relationship in
the grid view row modal.
* Made it possible to impersonate another user as premium admin.
* Made views trashable.
* New templates:
  * Brand Assets Manager
  * Business Conference
  * Car Hunt
  * Company Blog Management
  * Event Staffing
  * Hotel Bookings
  * Nonprofit Grant Tracker
  * Performance Reviews
  * Product Roadmap
  * Public Library Inventory
  * Remote Team Hub
  * Product Roadmap
  * Hotel Bookings
* Pin backend python dependencies using pip-tools.
* **Premium** Added row coloring.
* Prevent the Airtable import from failing hard when an invalid date is provided.
* Raise Airtable import task error and fixed a couple of minor import bugs.
* Scroll to the first error message if the form submission fail
* Select new view immediately after creation.
* Shared public forms now don't allow creating new options
for single and multiple select fields.
* Stopped the generated model cache clear operation also deleting all other redis keys.
* The standalone `baserow/backend` image when used to run a celery service now defaults
to running celery with the same number of processes as the number of available cores.
* Updated templates:
  * Book writing guide
  * Bucket List
  * Call Center Log
  * Company Asset Tracker
  * Email Marketing Campaigns
  * Home Inventory
  * House Search
  * Job Search
  * Nonprofit Organization Management
  * Personal Task Manager
  * Political Campaign Contributions
  * Project Tracker
  * Recipe Book
  * Restaurant Management
  * Single Trip Planner
  * Software Application Bug Tracker
  * Student Planner
  * Teacher Lesson Plans
  * Team Check-ins
  * University Admissions Management
  * Wedding Client Planner
* Upgraded node runtime to v16.14.0
* When the BASEROW_AMOUNT_OF_WORKERS env variable is set to blank, the amount of worker
processes defaults to the number of available cores.


## Released (2022-03-03_1.9.1)

### New features
* Fix the Baserow Heroku install filling up the hobby postgres by disabling template
syncing by default.
* Fixed API docs enum warnings. Removed `number_type` is no longer displayed in the API docs.
* Fixed bug when importing a formula or lookup field with an incorrect empty value.
* New templates:
  * Non-profit Organization Management
  * Elementary School Management
  * Call Center Log
  * Individual Medical Record
  * Trip History
  * Favorite Food Places
  * Wedding Client Planner
* Updated templates:
  * Holiday Shopping
  * Company Asset Tracker
  * Personal Health Log
  * Recipe Book
  * Student Planner
  * Political Campaign Contributions
* Upgraded `drf-spectacular`. Flag-style query parameters like `count` will now be displayed
as `boolean` instead of `any` in the OpenAPI documentation. However, the behavior of these
flags is still the same.


## Released (2022-03-02_1.9)

### New features
* Add footer aggregations to grid view
* Add health checks for all services.
* Add "insert left" and "insert right" field buttons to grid view head context buttons.
* Add Kanban view filters.
* Add the all-in-one Baserow docker image.
* Added accept `image/*` attribute to the form cover and logo upload.
* Added management to import a shared Airtable base.
* Added multi-cell selection and copying.
* Added search to gallery views.
* Added web-frontend interface to import a shared Airtable base.
* Allow for group registrations while public registration is closed
* Allow for signup via group invitation while public registration is closed.
* **breaking change** docker-compose.yml now requires secrets to be setup by the user,
listens by default on 0.0.0.0:80 with a Caddy reverse proxy, use BASEROW_PUBLIC_URL
and BASEROW_CADDY_ADDRESSES now to configure a domain with optional auto https.
* **breaking change** Number field has been changed and doesn't use `number_type` property
anymore. The property `number_decimal_places` can be now set to `0` to indicate integers
instead.
* Bumped some backend and web-frontend dependencies.
* Cache model fields when generating model.
* Ensure error logging is enabled in the Backend even when DEBUG is off.
* Fix Django's default index naming scheme causing index name collisions.
* Fix missing translation when importing empty CSV
* Fix restoring table linking to trashed tables creating invalid link field.
* Fixed `'<' not supported between instances of 'NoneType' and 'int'` error. Blank
string for a decimal value is now converted to `None` when using the REST API.
* Fixed adding new fields in the edit row popup that require refresh in Kanban and Form views.
* Fixed error when the select row modal is closed immediately after opening.
* Fixed not being able to create or convert a single select field with edge case name.
* Fixed OpenAPI spec. The specification is now valid and can be used for imports to other
tools, e.g. to various REST clients.
* Hide "Export view" button if there is no valid exporter available
* Migrate the Baserow Cloudron and Heroku images to work from the all-in-one.
* Moved the in component `<i18n>` translations to JSON files.
* Remove runtime mjml service and pre-render email templates at build time.
* Removed upload file size limit.
* Rework Baserow docker images so they can be built and tested by gitlab CI.
* Views supporting search are properly updated when a column with a matching default value is added.
* Workaround bug in Django's schema editor sometimes causing incorrect transaction
rollbacks resulting in the connection to the database becoming unusable.


## Released (2022-01-13_1.8.2)

### New features
* Fix Table Export showing blank modal.
* Fix vuelidate issues when baserow/web-frontend used as dependency.


## Released (2022-01-13_1.8.1)

### New features
* Fixed download/preview files from another origin
* Fixed migration failing when upgrading a version of Baserow installed using Postgres
10 or lower.


## Released (2022-01-13)

### New features
* Added ability to share grid views publicly.
* Added cover field to the Kanban view.
* Added day of month filter to date field.
* Added French translation.
* Added gallery view.
  * Added cover field to the gallery view.
* Added length is lower than filter.
* Added rating field type.
* Added Video, Audio, PDF and some Office file preview.
* Allow changing the text of the submit button in the form view.
* **breaking change** The API endpoint to rotate a form views slug has been moved to
`/database/views/${viewId}/rotate-slug/`.
* **dev.sh users** Fixed bug in dev.sh where UID/GID were not being set correctly,
please rebuild any dev images you are using.
* Fix bug where field options in rare situations could have been duplicated.
* Fix deleted options that appear in the command line JSON file export.
* Fix subtracting date intervals from dates in formulas in some situations not working.
* Fix the ability to make filters and sorts on invalid formula and lookup fields.
* Fixed bug preventing trash cleanup job from running after a lookup field was converted
to another field type.
* Fixed bug where not all rows were displayed on large screens.
* Fixed copying/pasting for date field.
* Fixed frontend errors occurring sometimes when mass deleting and restoring sorted
fields
* Fixed order of fields in form preview.
* Fixed reordering of single select options when initially creating the field.
* Focused the search field when opening the modal to link a table row.
* Improved performance by not rendering cells that are out of the view port.
* Increased maximum length of application name to 160 characters.
* New templates:
  * Car Maintenance Log
  * Teacher Lesson Plans
  * Business Conference Event
  * Restaurant Management
* Replaced the table `order` index with an `order, id` index to improve performance.
* Updated templates:
  * Healthcare Facility Management
  * Apartment Hunt
  * Recipe Book
  * Commercial Property Management


## Released (2021-11-25)

### New features
* Fix trashing tables and related link fields causing the field dependency graph to
become invalid.
* Fixed not executing premium tests.
* Increase Webhook URL max length to 2000.


## Released (2021-11-24)

### New features
* Add aggregate formula functions and the lookup formula function.
* Add lookup field type.
* Added a licensing system for the premium version.
* Added extra indexes for user tables increasing performance.
* Added table webhooks functionality.
* Added the kanban view.
* **Breaking Change**: Baserow's `docker-compose.yml` container names have changed to
no longer be hardcoded to prevent naming clashes.
* **Breaking Change**: Baserow's `docker-compose.yml` now allows setting the MEDIA_URL
env variable. If using MEDIA_PORT you now need to set MEDIA_URL also.
* Deprecate internal formula field function field_by_id.
* Fixed a bug where the frontend would fail hard if a table with no views was accessed.
* Fixed a bug where the frontend would fail hard when converting a multiple select field
inside the row edit modal.
* Fixed bug where it was possible to create duplicate trash entries.
* Fixed date_diff formula function.
* Fixed propType validation error when converting from a date field to a boolean field.
* Made it possible to change user information.
* New templates:
  * House Search
  * Personal Health Log
  * Job Search
  * Single Trip Planner
  * Software Application Bug Tracker
* Tables can now be opened in new browser tabs.
* Updated templates:
  * Commercial Property Management
  * Company Asset Tracker
  * Wedding Planner
  * Blog Post Management
  * Home Inventory
  * Book Writing Guide
  * Political Campaign Contributions
  * Applicant Tracker


## Released (2021-10-05)

### New features
* Added "Formula" field type with 30+ useful functions allowing dynamic per row
calculations.
* Added "Multiple Select" field type.
* Fix accidentally locking of too many rows in various tables during update operations.
* Fix minor error that could sometimes occur when a row and it's table/group/database
were deleted in rapid succession.
* Fixed a bug where the backend would fail hard when trying to order by field name without
using `user_field_names`.
* Fixed a bug where the currently selected view was not in the viewport of the parent.
* Fixed a bug where views context would not scroll down after a new view has been added.
* Fixed bug where a user could not be edited in the admin interface without providing
a password.
* Fixed bug where brand-new fields weren't included in view exports.
* Fixed bug where copying a cell containing a null value resulted in an error.
* Fixed bug where sometimes fields would not be ordered correctly in view exports.
* Fixed bug where the backend would fail hard when an invalid integer was provided as
'before_id' when moving a row by introducing a decorator to validate query parameters.
* Fixed error when pasting into a single select field.
* Fixed error when rapidly switching between template tables or views in the template
preview.
* Importing table data with a column name that is too long will now truncate that name.
* Introduced new endpoint to get and update user account information.
* Introduced the has file type filter.
* New templates:
  * Recipe Book
  * Healthcare Facility Management
  * Bucket List
  * Apartment Hunt
  * Holiday Shopping
  * Email Marketing Campaigns
  * Book Writing Guide
  * Home Inventory
  * Political Campaign Contributions
* Pasting the value of a single select option into a single select field now selects the
first option with that value.
* The API now returns appropriate errors when trying to create a field with a name which is too long.
* Updated templates:
  * Blog Post Management
* Upgraded Django to version 3.2.6 and also upgraded all other backend libraries to
their latest versions.


## Released (2021-08-11)

### New features
* Add backup and restore database management commands.
* Added "Last Modified" and "Created On" field types.
* Added password validation to password reset page.
* Added steps on how to configure Baserow to send emails in the install-on-ubuntu guide.
* Bumped the dependencies.
* Changed web-frontend `/api/docs` route into `/api-docs`.
* Dropped the `old_name` column.
* Enabled password validation in the backend.
* Fixed bug where the currently selected dropdown item is out of view from the dropdown
window when scrolling with the arrow keys.
* Fixed earliest and latest date aggregations
* Fixed moment issue if core is installed as a dependency.
* Fixed nuxt not restarting correctly using the provided Baserow supervisor config file.
* Hide view types that can't be exported in the export modal.
* Introduced link row field has row filter.
* Made it possible to leave a group.
* Made it possible to use the "F2"-Key to edit a cell without clearing the cell content.
* Made the form view compatible with importing and exporting.
* New templates:
  * Blog Post Management
* **Premium**: You can now comment and discuss rows with others in your group, click the
expand row button at the start of the row to view and add comments.
* Relaxed the URL field validator and made it consistent between the backend and
web-frontend.
* The internal setting allowing Baserow to run with the user tables in a separate
database has been removed entirely to prevent data integrity issues.
* Updated templates:
  * Personal Task Manager
  * Wedding Planning
  * Book Catalog
  * Applicant Tracker
  * Project Tracker


## Released (2021-07-16)

### New features
* Fix bug preventing fields not being able to be converted to link row fields in some
situations.


## Released (2021-07-15)

### New features
* **Breaking Change**: Baserow's `docker-compose.yml` no longer exposes ports for
the `db`, `mjml` and `redis` containers for security reasons.
* **Breaking Change**: `docker-compose.yml` will by default only expose Baserow on
`localhost` and not `0.0.0.0`, meaning it will not be accessible remotely unless
manually configured.


## Released (2021-07-13)

### New features
* Added a Heroku template and one click deploy button.
* Fixed bug preventing the deletion of rows with a blank single select primary field.
* Fixed error in trash cleanup job when deleting multiple rows and a field from the
same table at once.


## Released (2021-07-12)

### New features
* Add trash where deleted apps, groups, tables, fields and rows can be restored
deletion.
* Add user_field_names GET flag to various endpoints which switches the API to work
using actual field names and not the internal field_1,field_2 etc identifiers.
* Added before and after date filters.
* Added form view.
* Added templates:
  * Commercial Property Management
  * Company Asset Tracker
  * Student Planner
* Disallow duplicate field names in the same table, blank field names or field names
called 'order' and 'id'. Existing invalid field names will be fixed automatically.
* Fix the create group invite endpoint failing when no message provided.
* Made it possible to list table field meta-data with a token.
* Single select options can now be ordered by drag and drop.
* Support building Baserow out of the box on Ubuntu by lowering the required docker
version to build Baserow down to 19.03.
* The API endpoint to update the grid view field options has been moved to
`/api/database/views/{view_id}/field-options/`.
* The email field's validation is now consistent and much more permissive allowing most
values which look like email addresses.


## Released (2021-06-02)

### New features
* Added a human-readable error message when a user tries to sign in with a deactivated
account.
* Added a page containing external resources to the docs.
* Added today, this month and this year filter.
* Fixed bug where the focus of an Editable component was not always during and after
editing if the parent component had overflow hidden.
* Fixed bug where the grid view would fail hard if a cell is selected and the component
is destroyed.
* Fixed bug where the selected view would still be visible after deleting it.
* Made it possible to import a JSON file when creating a table.
* Made it possible to order the applications by drag and drop.
* Made it possible to order the groups by drag and drop.
* Made it possible to order the tables by drag and drop.
* Made it possible to order the views by drag and drop.
* **Premium**: Added an admin dashboard.
* **Premium**: Added group admin area allowing management of all baserow groups.
* **Premium** Tables and views can now be exported to JSON and XML.
* Removed URL field max length and fixed the backend failing hard because of that.
* Tables and views can now be exported to CSV (if you have installed using the ubuntu
guide please use the updated .conf files to enable this feature).
* Templates:
  * Lightweight CRM
  * Wedding Planning
  * Book Catalog
  * App Pitch Planner


## Released (2021-05-11)

### New features
* Added `--add-columns` flag to the `fill_table` management command. It creates all the
field types before filling the table with random data.
* Added configurable field limit.
* Added `fill_users` admin management command which fills baserow with fake users.
* Allow providing a `template_id` when registering a new account, which will install
that template instead of the default database.
* Fixed bug where the rows could get out of sync during real time collaboration.
* Fixed memory leak in the `link_row` field.
* Made it possible to drag and drop rows in the desired order.
* Made it possible to drag and drop the views in the desired order.
* Made it possible to export and import the file field including contents.
* Make the view header more compact when the content doesn't fit anymore.
* **Premium**: Added user admin area allowing management of all baserow users.
* Reworked Baserow's Docker setup to be easier to use, faster to build and more secure.
* Switch to using a celery based email backend by default.


## Released (2021-04-08)

### New features
* Add missing include query parameter and corresponding response attributes to API docs.
* Add Phone Number field.
* Add support for Date, Number and Single Select fields to the Contains and Not Contains
view
filters.
* Added gunicorn worker test to the CI pipeline.
* Added support for different** character encodings when importing CSV files.
* Added support for importing tables from XML files.
* Fixed 100X backend web socket errors when refreshing the page.
* Fixed bug where an invalid date could be converted to 0001-01-01.
* Fixed SSRF bug in the file upload by URL by blocking urls to the private network.
* Made it possible to re-order fields in a grid view.
* Prevent websocket reconnect loop when the authentication fails.
* Prevent websocket reconnect when the connection closes without error.
* Refactored the GridView component and improved interface speed.
* Remove incorrectly included "filters_disabled" field from
list_database_table_grid_view_rows api endpoint.
* Rename the "includes" get parameter across all API endpoints to "include" to be
consistent.
* Searching all rows can now be done by clicking the new search icon in the top right.
* Show an error to the user when the web socket connection could not be made and the
reconnect loop stops.
* Show the number of filters and sorts active in the header of a grid view.
* The first user to sign-up after installation now gets given staff status.
* The list_database_table_rows search query parameter now searches all possible field
types.


## Released (2021-03-01)

### New features
* Added a field type filename contains filter.
* Added Baserow Cloudron app.
* Added field name to the public REST API docs.
* Added single select field form option validation.
* Changed all cookies to SameSite=lax.
* Fail hard when the web-frontend can't reach the backend because of a network error.
* Fixed bug where a single select field without options could not be converted to a
another field.
* Fixed bug where the Editable component was not working if a prent a user-select:
none; property.
* Fixed error when a very long user file name is provided when uploading.
* Fixed the "Ignored attempt to cancel a touchmove" error.
* Made it possible for the admin to disable new signups.
* Made it possible to configure SMTP settings via environment variables.
* Made the public REST API docs compatible with smaller screens.
* Redesigned the left sidebar.
* Reduced the amount of queries when using the link row field.
* Refactored handler get_* methods so that they never check for permissions.
* Refactored the has_user everywhere such that the raise_error argument is used when
possible.
* Respect the date format when converting to a date field.
* Upgraded DRF Spectacular dependency to the latest version.
* Use UTC time in the date picker.


## Released (2021-02-04)

### New features
* Added option to hide fields in a grid view.
* Fixed bug where an incompatible row value was visible and used while changing the
field type.
* Fixed bug where is was not possible to create a relation to a table that has a single
select as primary field.
* Fixed bug where the row in the RowEditModel was not entirely reactive and wouldn't be
updated when the grid view was refreshed.
* Fixed bug where you could not convert an existing field to a single select field
without select options.
* Implemented real time collaboration.
* Keep token usage details.
* Made it possible to invite other users to a group.
* Upgraded web-frontend dependencies.


## Released (2021-01-06)

### New features
* Added filtering by GET parameter to the rows listing endpoint.
* Allow larger values for the number field and improved the validation.
* Fixed bug where if you have no filters, but the filter type is set to `OR` it always
results in a not matching row state in the web-frontend.
* Fixed bug where inserting above or below a row created upon signup doesn't work
correctly.
* Fixed bug where the arrow navigation didn't work for the dropdown component in
combination with a search query.
* Fixed bug where the page refreshes if you press enter in an input in the row modal.
* Fixed drifting context menu.
* Implemented a single select field.
* Made it possible to include or exclude specific fields when listing rows via the API.
* Made the file name editable.
* Made the rows orderable and added the ability to insert a row at a given position.
* Store updated and created timestamp for the groups, applications, tables, views,
fields and rows.


## Released (2020-12-01)

### New features
* Added community chat to the readme.
* Added select_for_update where it was still missing.
* Also lint the backend tests.
* Fixed API docs scrollbar size issue.
* Fixed bug where the sort choose field item didn't have a hover effect.
* Implemented a file field and user files upload.
* Implemented a switch to disable all filters without deleting them.
* Made it impossible for the `link_row` field to be a primary field because that can
cause the primary field to be deleted.
* Made it possible to order by fields via the rows listing endpoint.
* Made the cookies strict and secure.
* Removed the redundant _DOMAIN variables.
* Set un-secure lax cookie when public web frontend url isn't over a secure connection.


## Released (2020-11-02)

### New features
* Added ability to navigate dropdown menus with arrow keys.
* Added confirmation modals when the user wants to delete a group, application, table,
view or field.
* Added Email field.
* Added importer abstraction including a CSV and tabular paste importer.
* Added Ubuntu installation guide documentation.
* Fixed bug in the web-frontend URL validation where a '*' was invalidates.
* Fixed error when there is no view.
* Highlight the row of a selected cell.
* Made it possible to publicly expose the table data via a REST API.


## Released (2020-10-06)

### New features
* Added filtering of rows per view.
* Added sorting of rows per view.
* Added URL field.
* Fixed bug where the error message of the 'Select a table to link to' was not always
displayed.
* Fixed bug where the link row field is not removed from the store when the related
table is deleted.
* Fixed bug where the selected name of the dropdown was not updated when that name was
changed.
* Fixed The table X is not found in the store error.
* Prevent adding a new line to the long text field in the grid view when selecting the
cell by pressing the enter key.


## Released (2020-09-02)

### New features
* Added contribution guidelines.
* Fixed bug where it was not possible to change the table name when it contained a link
row field.


## Released (2020-08-31)

### New features
* Added field that can link to the row of another table.
* Block non web frontend domains in the base url when requesting a password reset
email.
* Fixed bug where the text_default value changed to None if not provided in a patch
request.
* Increased the amount of password characters to 256 when signing up.
* Show machine readable error message when the signature has expired.


## Released (2020-07-20)

### New features
* Added cookiecutter plugin boilerplate.
* Added documentation markdown files.
* Added OpenAPI docs.
* Added raises attribute to the docstrings.
* Fixed keeping the datepicker visible in the grid view when selecting a date for the
first time.
* Improved API 404 errors by providing a machine readable error.
* Refactored all SCSS classes to BEM naming.
* Removed not needed api v0 namespace in url and python module.
* Use the new long text field, date field and view's field options for the example
tables when creating a new account. Also use the long text field when creating a new
table.


## Released (2020-06-08)

### New features
* Added date/datetime field.
* Added long text field.
* Added row modal editing feature to the grid view.
* Added validation and formatting for the number field.
* Cancel the editing state of a fields when the escape key is pressed.
* Changed the styling of the notification alerts.
* Enabled the arrow keys to navigate through the fields in the grid view.
* Fill a newly created table with some initial data.
* Fixed error when changing field type and the data value wasn't in the correct
format.
* Fixed memory leak bug.
* Fixed not handling 500 errors.
* Fixed not refreshing token bug and improved authentication a little bit.
* Implemented password change function and settings popup.
* Implemented reset forgotten password functionality.
* Improved grid view scrolling for touch devices.
* Introduced copy, paste and delete functionality of selected fields.
* Made it possible to resize the field width per view.
* Normalize the users email address when signing up and signing in.
* Prevent row context menu when right clicking on a field that's being edited.
* The next field is now selected when the tab character is pressed when a field is
selected.
* Update the field's data values when the type changes.
* Use Django REST framework status code constants instead of integers.
* Use environment variables for all settings.


