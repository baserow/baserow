CORE_CONCEPTS = """
## CORE CONCEPTS

### Baserow Overview

• Baserow is organised into workspaces, each workspace has users invited to become collaborators
• Workspaces contain databases and builder applications
• On the free plan only 2 roles exist: admin and member
• Advanced/Enterprise plan adds more roles and permissions (RBAC): builder (replace member), editor, viewer, no access (to exclude resources)

### Key Features

• Instance level and workspace level user management, permissions and audit log
• Real-time collaboration
• Role-based access control (RBAC) with predefined roles and custom roles (advanced/enterprise)
• Notification panel for mentions in comments or rich text fields, workspace invites, and important updates
• Single sign-on (SSO) with SAML2, OIDC, and OAuth2 (advanced/enterprise)
• Model Context Protocol (MCP) to connect AI tools to Baserow data
• API specification: https://api.baserow.io/api/schema.json
* You cannot create new workspaces. You're forced to use the workspace in the UI context, but you can create new databases within it.
"""

DATABASE_BUILDER_CONCEPTS = """
## DATABASE BUILDER CONCEPTS

**Module:** "database"

### Hierarchy

Workspace → Database (1:N) → Tables (1:N) → Fields, Rows, Views, Webhooks (1:N each)
    Views → Filters, Sorts, GroupBy, Row colors (1:N each)
    Rows → Row comments (1:N)

### Key Relationships

• Fields define table schema; Views present table data
• View configs (Filters/Sorts/GroupBy/Row colors) reference Fields to control row visibility and order
• All rows conform to table's schema
• link_row fields create relationships between tables (requires target table)
• Every table has only one field set as primary field (only subset of field types can be primary)
• Data sync: sync a baserow table with another table or external source
• Snapshot: backup of a database, can be restored later (multiple per database)
• Webhooks: triggered on row/field events (created, updated, deleted, etc.)
• Field permissions: restrict who can edit values in that field
• View can show/hide fields
• Views can be publicly shared with public link and optional password
• Views default to collaborative (all workspace users); can be personal (creator only)
• Users can add comments to rows and reply with mentions
• RBAC at workspace, database, table and field level (advanced/enterprise)
• Database tokens for secure API access

### Field Types

**Text & Content:**
• text, long_text (+rich?), url, email, phone_number, password

**Numbers & Logic:**
• number (decimals, prefix/suffix), rating, boolean, duration (format)

**Dates & Time:**
• date (+time?), last_modified (+time?)*, created_on (+time?)*

**Users & Collaboration:**
• last_modified_by*, created_by*, multiple_collaborators

**Relationships & Files:**
• link_row (→table), file

**Selections:**
• single_select (options), multiple_select (options)

**Computed Fields:**
• formula*, count* (→link_row), rollup* (→link_row, target_field, aggregation)
• lookup* (→link_row, target_field), uuid*, autonumber*, ai (prompt)

*read-only fields

### View Types

• **grid** - default tabular view
• **form** - data entry interface
• **gallery** - cards with cover images
• **kanban** - requires single_select field
• **calendar** - requires date field
• **timeline** - requires 2 date fields (start and end)
"""

APPLICATION_BUILDER_CONCEPTS = """
## APPLICATION BUILDER CONCEPTS

**Module:** "application builder"

### Hierarchy

Workspace → Builder Application (1:N) → Pages (1:N) → Elements, Data Sources, Workflows (1:N each)
    Elements → Events/Actions, Style Properties, Visibility Rules (1:N each)
    Data Sources → Filters, Field Mappings (1:N each)

### Key Relationships

• Pages define routes with path and parameters; Elements compose the UI
• Data Sources connect pages to database tables/views, enabling dynamic content
• Workflows triggered by element events execute actions (create/update rows, navigate, notify)
• Elements can bind to data sources for dynamic values
• Domains required for publishing applications

### Element Types

#### Display Elements
• **heading** - size, alignment, color
• **text** - content, formatting, data binding
• **link** - url, target, navigation type
• **image** - source, alt text, alignment
• **iframe** - url, height

#### Input Elements
• **text_input** - placeholder, validation, required
• **choice** - options (dropdown/radio), data source
• **checkbox** - default value
• **date_time_picker** - format, time enabled
• **rating** - max value, icon
• **file_input*** - accept types, max size

#### Layout Elements
• **columns** - responsive breakpoints, gap
• **repeat** - data source, orientation
• **multi_page_container*** - tabs/steps
• **menu*** - items, orientation

#### Interactive Elements
• **button** - text, width, alignment → action
• **form** - fields[], submit button → action
• **table** - fields[], layout, filterable, sortable, searchable
• **record_selector*** - data source, display field
• **login*** - auth provider → redirect

*advanced/enterprise features

### Event/Action Types

• **show_notification** - message, type
• **open_page** - → page/url, parameters
• **create_row** - → table, field mappings [requires integration]
• **update_row** - → table, row_id, field mappings [requires integration]
• **logout** - → redirect page

### Data Source Configuration

• **table** - → database.table
• **view** - → table.view
• **filters** - field conditions
• **search** - query parameter
• **order_by** - field, direction

### Publishing

• **domain** - subdomain/custom
• **SSL certificate** - automatic provisioning
• **environment** - development/production
"""
