#!/usr/bin/env python3
"""
Complete Baserow documentation fetcher with TOC removal
Fetches all Baserow documentation pages and removes repetitive table of contents
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from html2text import HTML2Text
from pathlib import Path

# COMPLETE Baserow documentation URLs (194+ pages from our final fetch)
DOCS_URLS = [
    # Getting Started (6 pages)
    ("getting-started/index.md", "https://baserow.io/user-docs"),
    ("getting-started/baserow-basics.md", "https://baserow.io/user-docs/baserow-basics"),
    ("getting-started/how-to-get-started.md", "https://baserow.io/user-docs/how-to-get-started-with-baserow"),
    ("getting-started/set-up-baserow.md", "https://baserow.io/user-docs/set-up-baserow"),
    ("getting-started/learn-baserow-basic-concepts.md", "https://baserow.io/user-docs/learn-baserow-basic-concepts"),
    ("getting-started/keyboard-shortcuts.md", "https://baserow.io/user-docs/baserow-keyboard-shortcuts"),
    
    # Workspaces (6 pages)
    ("workspace/intro-to-workspaces.md", "https://baserow.io/user-docs/intro-to-workspaces"),
    ("workspace/setting-up-a-workspace.md", "https://baserow.io/user-docs/setting-up-a-workspace"),
    ("workspace/export-workspaces.md", "https://baserow.io/user-docs/export-workspaces"),
    ("workspace/import-workspaces.md", "https://baserow.io/user-docs/import-workspaces"),
    ("workspace/leave-workspace.md", "https://baserow.io/user-docs/leave-a-workspace"),
    ("workspace/delete-workspace.md", "https://baserow.io/user-docs/delete-a-workspace"),
    
    # Databases (5 pages)
    ("database/intro-to-databases.md", "https://baserow.io/user-docs/intro-to-databases"),
    ("database/create-database.md", "https://baserow.io/user-docs/create-a-database"),
    ("database/add-from-template.md", "https://baserow.io/user-docs/add-database-from-template"),
    ("database/import-airtable.md", "https://baserow.io/user-docs/import-airtable-to-baserow"),
    ("database/delete-database.md", "https://baserow.io/user-docs/delete-a-database"),
    
    # Tables (8 pages)
    ("tables/intro-to-tables.md", "https://baserow.io/user-docs/intro-to-tables"),
    ("tables/create-table.md", "https://baserow.io/user-docs/create-a-table"),
    ("tables/create-table-via-import.md", "https://baserow.io/user-docs/create-a-table-via-import"),
    ("tables/data-sync.md", "https://baserow.io/user-docs/data-sync-in-baserow"),
    ("tables/import-data-existing-table.md", "https://baserow.io/user-docs/import-data-into-an-existing-table"),
    ("tables/customize-table.md", "https://baserow.io/user-docs/customize-a-table"),
    ("tables/export-tables.md", "https://baserow.io/user-docs/export-tables"),
    ("tables/delete-table.md", "https://baserow.io/user-docs/delete-a-table"),
    
    # Fields - General (10 pages)
    ("fields/field-overview.md", "https://baserow.io/user-docs/baserow-field-overview"),
    ("fields/adding-field.md", "https://baserow.io/user-docs/adding-a-field"),
    ("fields/field-customization.md", "https://baserow.io/user-docs/field-customization"),
    ("fields/filters-in-baserow.md", "https://baserow.io/user-docs/filters-in-baserow"),
    ("fields/advanced-filtering.md", "https://baserow.io/user-docs/advanced-filtering"),
    ("fields/working-with-timezones.md", "https://baserow.io/user-docs/working-with-timezones"),
    ("fields/footer-aggregation.md", "https://baserow.io/user-docs/footer-aggregation"),
    ("fields/group-rows.md", "https://baserow.io/user-docs/group-rows-in-baserow"),
    ("fields/field-indexes.md", "https://baserow.io/user-docs/field-indexes"),
    ("fields/field-value-constraints.md", "https://baserow.io/user-docs/field-value-constraints"),
    
    # Field Types - All 26 field types!
    ("field-types/primary-field.md", "https://baserow.io/user-docs/primary-field"),
    ("field-types/single-line-text-field.md", "https://baserow.io/user-docs/single-line-text-field"),
    ("field-types/long-text-field.md", "https://baserow.io/user-docs/long-text-field"),
    ("field-types/number-field.md", "https://baserow.io/user-docs/number-field"),
    ("field-types/rating-field.md", "https://baserow.io/user-docs/rating-field"),
    ("field-types/boolean-field.md", "https://baserow.io/user-docs/boolean-field"),
    ("field-types/date-time-fields.md", "https://baserow.io/user-docs/date-and-time-fields"),
    ("field-types/url-field.md", "https://baserow.io/user-docs/url-field"),
    ("field-types/email-field.md", "https://baserow.io/user-docs/email-field"),
    ("field-types/file-field.md", "https://baserow.io/user-docs/file-field"),
    ("field-types/single-select-field.md", "https://baserow.io/user-docs/single-select-field"),
    ("field-types/multiple-select-field.md", "https://baserow.io/user-docs/multiple-select-field"),
    ("field-types/phone-number-field.md", "https://baserow.io/user-docs/phone-number-field"),
    ("field-types/link-to-table-field.md", "https://baserow.io/user-docs/link-to-table-field"),
    ("field-types/lookup-field.md", "https://baserow.io/user-docs/lookup-field"),
    ("field-types/collaborator-field.md", "https://baserow.io/user-docs/collaborator-field"),
    ("field-types/count-field.md", "https://baserow.io/user-docs/count-field"),
    ("field-types/rollup-field.md", "https://baserow.io/user-docs/rollup-field"),
    ("field-types/created-by-field.md", "https://baserow.io/user-docs/created-by-field"),
    ("field-types/last-modified-by-field.md", "https://baserow.io/user-docs/last-modified-by-field"),
    ("field-types/last-modified-field.md", "https://baserow.io/user-docs/last-modified-field"),
    ("field-types/duration-field.md", "https://baserow.io/user-docs/duration-field"),
    ("field-types/autonumber-field.md", "https://baserow.io/user-docs/autonumber-field"),
    ("field-types/uuid-field.md", "https://baserow.io/user-docs/uuid-field"),
    ("field-types/password-field.md", "https://baserow.io/user-docs/password-field"),
    ("field-types/ai-field.md", "https://baserow.io/user-docs/ai-field"),
    
    # Formula (3 pages)
    ("formulas/formula-field-overview.md", "https://baserow.io/user-docs/formula-field-overview"),
    ("formulas/understanding-formulas.md", "https://baserow.io/user-docs/understanding-formulas"),
    ("formulas/generate-formulas-with-ai.md", "https://baserow.io/user-docs/generate-formulas-with-baserow-ai"),
    
    # Views - General (6 pages)
    ("views/overview-of-views.md", "https://baserow.io/user-docs/overview-of-baserow-views"),
    ("views/create-custom-views.md", "https://baserow.io/user-docs/create-custom-views-of-your-data"),
    ("views/collaborative-views.md", "https://baserow.io/user-docs/collaborative-views"),
    ("views/personal-views.md", "https://baserow.io/user-docs/personal-views"),
    ("views/view-customization.md", "https://baserow.io/user-docs/view-customization"),
    ("views/export-view.md", "https://baserow.io/user-docs/export-a-view"),
    
    # View Types - All 7 view types
    ("view-types/grid-view.md", "https://baserow.io/user-docs/guide-to-grid-view"),
    ("view-types/gallery-view.md", "https://baserow.io/user-docs/guide-to-gallery-view"),
    ("view-types/form-view.md", "https://baserow.io/user-docs/guide-to-creating-forms-in-baserow"),
    ("view-types/form-survey-mode.md", "https://baserow.io/user-docs/form-survey-mode"),
    ("view-types/kanban-view.md", "https://baserow.io/user-docs/guide-to-kanban-view"),
    ("view-types/calendar-view.md", "https://baserow.io/user-docs/guide-to-calendar-view"),
    ("view-types/timeline-view.md", "https://baserow.io/user-docs/guide-to-timeline-view"),
    
    # Rows (8 pages)
    ("rows/overview-of-rows.md", "https://baserow.io/user-docs/overview-of-rows"),
    ("rows/create-row.md", "https://baserow.io/user-docs/how-to-make-new-rows"),
    ("rows/paste-data-into-cells.md", "https://baserow.io/user-docs/paste-data-into-baserow-table"),
    ("rows/row-configurations.md", "https://baserow.io/user-docs/navigating-row-configurations"),
    ("rows/enlarging-rows.md", "https://baserow.io/user-docs/enlarging-rows"),
    ("rows/row-coloring.md", "https://baserow.io/user-docs/row-coloring"),
    ("rows/row-commenting.md", "https://baserow.io/user-docs/row-commenting"),
    ("rows/row-change-history.md", "https://baserow.io/user-docs/row-change-history"),
    
    # Collaboration (7 pages)
    ("collaboration/managing-collaborators.md", "https://baserow.io/user-docs/managing-workspace-collaborators"),
    ("collaboration/working-with-collaborators.md", "https://baserow.io/user-docs/working-with-collaborators"),
    ("collaboration/manage-workspace-permissions.md", "https://baserow.io/user-docs/manage-workspace-permissions"),
    ("collaboration/public-sharing.md", "https://baserow.io/user-docs/public-sharing"),
    ("collaboration/remove-user-from-workspace.md", "https://baserow.io/user-docs/remove-a-user-from-a-workspace"),
    ("collaboration/create-manage-teams.md", "https://baserow.io/user-docs/create-and-manage-teams"),
    ("collaboration/notifications.md", "https://baserow.io/user-docs/notifications"),
    
    # Role-based Permissions (8 pages)
    ("security/permissions-overview.md", "https://baserow.io/user-docs/permissions-overview"),
    ("security/rbac.md", "https://baserow.io/user-docs/role-based-access-control-rbac"),
    ("security/permission-levels.md", "https://baserow.io/user-docs/set-permission-level"),
    ("security/assign-roles-workspace-members.md", "https://baserow.io/user-docs/assign-roles-to-members-at-workspace-level"),
    ("security/assign-roles-workspace-teams.md", "https://baserow.io/user-docs/assign-roles-to-teams-at-workspace-level"),
    ("security/assign-roles-database-level.md", "https://baserow.io/user-docs/assign-roles-at-database-level"),
    ("security/assign-roles-table-level.md", "https://baserow.io/user-docs/assign-roles-at-table-level"),
    ("security/field-level-permissions.md", "https://baserow.io/user-docs/field-level-permissions"),
    
    # Integrations (10 pages)
    ("integrations/webhooks.md", "https://baserow.io/user-docs/webhooks"),
    ("integrations/database-tokens.md", "https://baserow.io/user-docs/personal-api-tokens"),
    ("integrations/database-api.md", "https://baserow.io/user-docs/database-api"),
    ("integrations/database-table-id.md", "https://baserow.io/user-docs/database-and-table-id"),
    ("integrations/zapier.md", "https://baserow.io/user-docs/zapier"),
    ("integrations/make.md", "https://baserow.io/user-docs/make"),
    ("integrations/n8n.md", "https://baserow.io/user-docs/n8n"),
    ("integrations/tooljet.md", "https://baserow.io/user-docs/tooljet"),
    ("integrations/pipedream.md", "https://baserow.io/user-docs/pipedream"),
    ("integrations/suretriggers.md", "https://baserow.io/user-docs/suretriggers-integration"),
    
    # Account Settings (5 pages)
    ("account/account-settings-overview.md", "https://baserow.io/user-docs/account-settings-overview"),
    ("account/password-management.md", "https://baserow.io/user-docs/password-management"),
    ("account/data-recovery-deletion.md", "https://baserow.io/user-docs/data-recovery-and-deletion"),
    ("account/delete-account.md", "https://baserow.io/user-docs/delete-your-baserow-account"),
    ("account/snapshots.md", "https://baserow.io/user-docs/snapshots"),
    
    # Billing (6 pages)
    ("billing/subscriptions-overview.md", "https://baserow.io/user-docs/subscriptions-overview"),
    ("billing/pricing-plans.md", "https://baserow.io/user-docs/pricing-plans"),
    ("billing/buying-subscription.md", "https://baserow.io/user-docs/buying-a-subscription"),
    ("billing/instance-id.md", "https://baserow.io/user-docs/getting-and-changing-the-instance-id"),
    ("billing/change-subscription.md", "https://baserow.io/user-docs/change-a-paid-subscription"),
    ("billing/premium-license.md", "https://baserow.io/user-docs/get-a-licence-key"),
    
    # Enterprise Version (7 pages)
    ("enterprise/license-overview.md", "https://baserow.io/user-docs/enterprise-license-overview"),
    ("enterprise/admin-panel.md", "https://baserow.io/user-docs/enterprise-admin-panel"),
    ("enterprise/activate-license.md", "https://baserow.io/user-docs/activate-enterprise-license"),
    ("admin/admin-panel-users.md", "https://baserow.io/user-docs/admin-panel-users"),
    ("admin/admin-panel-workspaces.md", "https://baserow.io/user-docs/admin-panel-workspaces"),
    ("admin/admin-panel-audit-logs.md", "https://baserow.io/user-docs/admin-panel-audit-logs"),
    ("admin/admin-panel-settings.md", "https://baserow.io/user-docs/admin-panel-settings"),
    
    # Enterprise SSO (11 pages)
    ("sso/sso-overview.md", "https://baserow.io/user-docs/single-sign-on-sso-overview"),
    ("sso/enable-sso.md", "https://baserow.io/user-docs/enable-single-sign-on-sso"),
    ("sso/configure-okta.md", "https://baserow.io/user-docs/configure-sso-with-okta"),
    ("sso/configure-onelogin.md", "https://baserow.io/user-docs/configure-sso-with-onelogin"),
    ("sso/configure-azure-ad.md", "https://baserow.io/user-docs/configure-sso-with-azure-ad"),
    ("sso/configure-google.md", "https://baserow.io/user-docs/configure-google-for-oauth-2-sso"),
    ("sso/configure-facebook.md", "https://baserow.io/user-docs/configure-facebook-for-oauth-2-sso"),
    ("sso/configure-github.md", "https://baserow.io/user-docs/configure-github-for-oauth-2-sso"),
    ("sso/configure-gitlab.md", "https://baserow.io/user-docs/configure-gitlab-for-oauth-2-sso"),
    ("sso/configure-openid.md", "https://baserow.io/user-docs/configure-openid-connect-for-oauth-2-sso"),
    ("sso/email-password-auth.md", "https://baserow.io/user-docs/email-and-password-authentication"),
    
    # Application Builder - Core (8 pages)
    ("app-builder/overview.md", "https://baserow.io/user-docs/application-builder-overview"),
    ("app-builder/create-application.md", "https://baserow.io/user-docs/create-an-application"),
    ("app-builder/configuration.md", "https://baserow.io/user-docs/application-builder-configuration"),
    ("app-builder/preview-publish.md", "https://baserow.io/user-docs/preview-and-publish-application"),
    ("app-builder/application-settings.md", "https://baserow.io/user-docs/application-settings"),
    ("app-builder/add-domain.md", "https://baserow.io/user-docs/add-a-domain-to-an-application"),
    ("app-builder/user-sources.md", "https://baserow.io/user-docs/user-sources"),
    ("app-builder/custom-css-js.md", "https://baserow.io/user-docs/custom-css-and-javascript"),
    
    # Application Builder Editor (3 pages)
    ("app-builder/pages.md", "https://baserow.io/user-docs/pages-in-the-application-builder"),
    ("app-builder/data-sources.md", "https://baserow.io/user-docs/data-sources"),
    ("app-builder/page-settings.md", "https://baserow.io/user-docs/application-builder-page-settings"),
    
    # Application Builder Elements (24+ pages)
    ("app-builder/elements-overview.md", "https://baserow.io/user-docs/elements-overview"),
    ("app-builder/add-remove-elements.md", "https://baserow.io/user-docs/add-and-remove-elements"),
    ("app-builder/element-style.md", "https://baserow.io/user-docs/element-style"),
    ("app-builder/element-events.md", "https://baserow.io/user-docs/element-events"),
    ("app-builder/element-visibility.md", "https://baserow.io/user-docs/application-builder-element-visibility"),
    ("app-builder/heading-element.md", "https://baserow.io/user-docs/application-builder-heading-element"),
    ("app-builder/text-element.md", "https://baserow.io/user-docs/application-builder-text-element"),
    ("app-builder/link-element.md", "https://baserow.io/user-docs/application-builder-link-element"),
    ("app-builder/image-element.md", "https://baserow.io/user-docs/application-builder-image-element"),
    ("app-builder/text-input-element.md", "https://baserow.io/user-docs/application-builder-text-input-element"),
    ("app-builder/columns-element.md", "https://baserow.io/user-docs/application-builder-columns-element"),
    ("app-builder/button-element.md", "https://baserow.io/user-docs/application-builder-button-element"),
    ("app-builder/table-element.md", "https://baserow.io/user-docs/application-builder-table-element"),
    ("app-builder/form-element.md", "https://baserow.io/user-docs/application-builder-form-element"),
    ("app-builder/dropdown-element.md", "https://baserow.io/user-docs/application-builder-dropdown-element"),
    ("app-builder/checkbox-element.md", "https://baserow.io/user-docs/application-builder-checkbox-element"),
    ("app-builder/iframe-element.md", "https://baserow.io/user-docs/application-builder-iframe-element"),
    ("app-builder/login-element.md", "https://baserow.io/user-docs/application-builder-login-element"),
    ("app-builder/repeat-element.md", "https://baserow.io/user-docs/application-builder-repeat-element"),
    ("app-builder/record-selector-element.md", "https://baserow.io/user-docs/application-builder-record-selector-element"),
    ("app-builder/date-time-picker-element.md", "https://baserow.io/user-docs/application-builder-date-time-picker-element"),
    ("app-builder/multi-page-container.md", "https://baserow.io/user-docs/application-builder-multi-page-container"),
    ("app-builder/menu-element.md", "https://baserow.io/user-docs/menu-element"),
    ("app-builder/rating-element.md", "https://baserow.io/user-docs/application-builder-rating-element"),
    ("app-builder/file-input-element.md", "https://baserow.io/user-docs/application-builder-file-input-element"),
    
    # Dashboards (2 pages)
    ("dashboards/overview.md", "https://baserow.io/user-docs/dashboards-overview"),
    ("dashboards/create-dashboard.md", "https://baserow.io/user-docs/create-a-dashboard"),
    
    # MCP Server (1 page)
    ("mcp/mcp-server.md", "https://baserow.io/user-docs/mcp-server"),
]


def fetch_and_convert_to_markdown(url):
    """Fetch a URL and convert its content to markdown"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Try to find the main content area
        content = None

        # Common content selectors for documentation sites
        selectors = [
            "main",
            "article",
            ".content",
            ".docs-content",
            ".documentation",
            "#content",
            ".nuxt-content",
            ".page-content",
            '[role="main"]',
        ]

        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                break

        # If no specific content area found, try to get body
        if not content:
            content = soup.find("body")

        if not content:
            print(f"Warning: Could not find content area for {url}")
            return None

        # Remove script and style elements
        for script in content(["script", "style"]):
            script.decompose()

        # Convert to markdown
        h2t = HTML2Text()
        h2t.ignore_links = False
        h2t.ignore_images = False
        h2t.body_width = 0  # Don't wrap lines

        markdown = h2t.handle(str(content))

        # Clean up the markdown
        # Remove excessive blank lines
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)

        # Add a header with the source URL
        header = f"# Baserow Documentation\n\nSource: {url}\n\n---\n\n"

        return header + markdown

    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def remove_table_of_contents(content, is_index_file=False):
    """
    Remove repetitive table of contents from documentation, keeping it only in index
    
    Args:
        content (str): The markdown content
        is_index_file (bool): True if this is the main index file (keep TOC)
        
    Returns:
        str: Content with TOC removed (unless it's the index file)
    """
    if is_index_file:
        # Keep the full TOC in the main index file
        return content
    
    lines = content.split('\n')
    cleaned_lines = []
    in_navigation = False
    skip_until_content = False
    
    for i, line in enumerate(lines):
        # Detect start of navigation menu (after the header and logo)
        if '[![Baserow logo]' in line:
            cleaned_lines.append(line)  # Keep the logo line
            skip_until_content = True
            continue
            
        # Skip navigation links and nested lists
        if skip_until_content:
            # Look for the actual content start - usually after the navigation
            # Skip lines that are clearly part of navigation
            if (line.strip().startswith('* ') or 
                line.strip().startswith('- ') or
                line.strip().startswith('[') or
                line.strip() == '' or
                '/user-docs/' in line):
                continue
            else:
                # Found the start of actual content
                skip_until_content = False
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def remove_still_need_help_section(content):
    """
    Remove the 'Still need help?' section from the end of documentation files
    
    Args:
        content (str): The markdown content
        
    Returns:
        str: Content with 'Still need help?' section removed
    """
    lines = content.split('\n')
    cleaned_lines = []
    
    # Find where "Still need help?" starts
    still_need_help_index = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('Still need help?'):
            still_need_help_index = i
            break
    
    if still_need_help_index == -1:
        # No "Still need help?" section found, return original content
        return content
    
    # Keep everything before "Still need help?"
    cleaned_lines = lines[:still_need_help_index]
    
    # Remove trailing empty lines
    while cleaned_lines and cleaned_lines[-1].strip() == '':
        cleaned_lines.pop()
    
    return '\n'.join(cleaned_lines)


def clean_existing_docs():
    """Remove TOC and 'Still need help?' sections from all existing documentation files"""
    base_dir = Path("docs")
    if not base_dir.exists():
        return
    
    print("🧹 Cleaning existing documentation files...")
    toc_cleaned_count = 0
    help_cleaned_count = 0
    
    for md_file in base_dir.glob("**/*.md"):
        # Check if this is the main index file
        is_index = md_file.name == "index.md" and md_file.parent.name == "getting-started"
        
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Remove TOC first
            cleaned_content = remove_table_of_contents(content, is_index)
            if cleaned_content != content:
                toc_cleaned_count += 1
            
            # Then remove "Still need help?" section
            final_content = remove_still_need_help_section(cleaned_content)
            if final_content != cleaned_content:
                help_cleaned_count += 1
            
            # Only write if content changed
            if final_content != content:
                with open(md_file, "w", encoding="utf-8") as f:
                    f.write(final_content)
                print(f"  ✅ Cleaned {md_file.relative_to(base_dir)}")
            
        except Exception as e:
            print(f"  ❌ Error cleaning {md_file}: {e}")
    
    print(f"🧹 Cleaned TOC from {toc_cleaned_count} files")
    print(f"🧹 Cleaned 'Still need help?' from {help_cleaned_count} files")


def main():
    base_dir = Path("docs")
    base_dir.mkdir(parents=True, exist_ok=True)

    successful = 0
    failed = 0
    skipped = 0
    
    print(f"🚀 COMPLETE Baserow Documentation Fetch & Clean")
    print(f"📚 Total pages to fetch: {len(DOCS_URLS)}")
    print()

    for i, (filepath, url) in enumerate(DOCS_URLS, 1):
        file_path = base_dir / filepath
        
        # Skip if file already exists and user didn't request refresh
        if file_path.exists():
            print(f"[{i:3d}/{len(DOCS_URLS):3d}] Skipping (exists): {filepath}")
            skipped += 1
            continue
            
        print(f"[{i:3d}/{len(DOCS_URLS):3d}] Fetching: {url}")

        # Create subdirectories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Fetch and convert content
        markdown_content = fetch_and_convert_to_markdown(url)

        if markdown_content:
            # Determine if this is the main index file
            is_index = filepath == "getting-started/index.md"
            
            # Remove TOC from content (except main index)
            cleaned_content = remove_table_of_contents(markdown_content, is_index)
            
            # Remove "Still need help?" section
            final_content = remove_still_need_help_section(cleaned_content)
            
            # Save to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(final_content)
            print(f"  ✅ Saved {'(TOC preserved)' if is_index else '(TOC & help section removed)'} to {filepath}")
            successful += 1
        else:
            print(f"  ❌ Failed to fetch content")
            failed += 1

        # Be polite and don't hammer the server
        time.sleep(0.5)

    print(f"\n" + "="*60)
    print(f"🎉 COMPLETE DOCUMENTATION FETCH SUMMARY")
    print(f"="*60)
    print(f"✅ Successfully fetched: {successful}")
    print(f"⏭️  Skipped (already existed): {skipped}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total processed: {successful + skipped + failed}")
    
    # Clean existing files if any were skipped
    if skipped > 0:
        print(f"\n🧹 Cleaning TOC from existing files...")
        clean_existing_docs()
    
    # Final count
    total_files = len(list(base_dir.glob("**/*.md")))
    print(f"\n📚 FINAL DOCUMENTATION COUNT: {total_files} files")
    print(f"🎯 Complete Baserow knowledge base ready for AI assistant!")


if __name__ == "__main__":
    main()