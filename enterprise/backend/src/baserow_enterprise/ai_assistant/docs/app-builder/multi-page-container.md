# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-multi-page-container

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Application Builder - Multi-page header and footer elements

Multi-page header and footer elements allow you to create reusable containers that can be applied across multiple pages of your application.

This streamlines your workflow by allowing you to define a consistent structure once and apply it throughout your application. This not only saves time but also ensures design consistency.

![Image: Baserow multipage header and footer](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/c4f30052-7e54-4083-834f-9eef7429b5fb/multi_page_header_and_footer_elements.webp)

## Overview

The header and footer elements are perfect for common page elements like navigation bars, branding, or footer information.

With the reusable design, you can apply the same header or footer to multiple pages, update it once, and changes reflect across all linked pages.

You can configure styling and layout using the element settings. For further details, refer to the [element style customization guide](/user-docs/element-style).

## Add a multi-page container

To add the multi-page header or multi-page footer to a [page](/user-docs/pages-in-the-application-builder):

  1. Open the elements panel from the page editor interface.
  2. Scroll through the list or search for: 
     * **Multi-page header** to add a reusable header: Add navigation menus, logos, or search bars to all pages.
     * **Multi-page footer** to add a reusable footer: Include contact information, links to privacy policies, or copyright text.
  3. Select to add the desired element to the page.

## Configure the multi-page element

The header will automatically position itself at the top of the page. The footer will automatically position itself at the bottom of the page.

Once you’ve added the header or footer, you can customize how and where it appears.

### Display settings

You have three options to configure visibility where headers or footers appear across your pages:

  1. **On all pages**

The element appears on every page within your application.

  2. **Only on selected pages**

You can choose specific pages where the element should appear. A list of all pages will be displayed for easy selection. For example, apply a footer only to specific content pages like About or Contact.

  3. **Exclude selected pages**

The element will appear on all pages except those you select. For example, exclude the header from a login page or a specialized landing page.

### Steps to configure display settings

  1. Click on the **Multi-page header** or **Multi-page footer** element in the editor.
  2. Open the **General settings** panel.
  3. Under the **Display** section, choose one of the following display settings: 
     * On all pages
     * Only on selected pages
     * Exclude selected pages
  4. For selective options, use the displayed list to check/uncheck pages as needed.

For more design control, combine multi-page headers/footers with elements like [columns](/user-docs/application-builder-columns-element) or [buttons](/user-docs/application-builder-button-element) for dynamic layouts.

You can [edit or update](/user-docs/elements-overview) the multi-page elements at any time; changes are reflected across all pages where they are applied.

## Related content

  * [Customizing element style](/user-docs/element-style)
  * [Managing page layouts and elements](/user-docs/elements-overview)

