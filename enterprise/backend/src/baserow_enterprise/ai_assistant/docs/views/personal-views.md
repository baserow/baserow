# Baserow Documentation

Source: https://baserow.io/user-docs/personal-views

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Personal views

This section provides a guide to Personal views. To learn more about views in general, check out this [support article](/user-docs/create-custom-views-of-your-data).

> Personal views are a premium feature available for [Premium, Advanced, and Enterprise plans](/user-docs/pricing-plans).

![Personal views](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/dd0ed15e-fb8c-4d64-9beb-1e5ee3610a7a/Screenshot_2023-03-07_at_18.12.46.png)

When creating a new view, you can choose from the two view permission types:

  1. [Collaborative views](/user-docs/collaborative-views): Collaborative views are visible and configurable by all [workspace members](/user-docs/working-with-collaborators).
  2. Personal views: Personal views are only visible to the user creating them.

You can change the view type from collaborative to personal or vice versa. Simply click on the ellipsis ••• next to the desired view and select the option to change the view type.

## Overview

Personal views are a type of view configuration that allows you to create your own, personal views, separate from shared collaborative views.

Personal views enable [workspace members with the right permission](/user-docs/working-with-collaborators) to create views that can only be viewed and modified by the view’s owner. Only the owner of a personal view can change the [filters](/user-docs/field-customization), [field visibility, field order](/user-docs/field-customization), sorts, [row heights](/user-docs/navigating-row-configurations), and [row coloring](/user-docs/row-coloring) of that view.

> You cannot make the only view in a table into a personal view. There must always be at least one [collaborative view](/user-docs/collaborative-views) available to everyone in the workspace.

Personal views are extremely useful for filtering or sort a table’s data without affecting the configurations of your collaborators. For example, you could create a personal view with filters to only show your tasks with the highest priority that are assigned to you. You can prevent other collaborators from accidentally changing your views by making the view personal rather than [collaborative](/user-docs/collaborative-views).

## Create a personal view

From the top of the table, select the view switcher at the top of the table to reveal the view dropdown. The options will appear in the View menu at the top of your screen. Go down to the second half of the view dropdown

Select a view type from the options presented for the type of view you’d like to create.

Click on a view type to open up the menu to create your new view. Choose ‘Personal’ as the [view permission type](/user-docs/collaborative-views). Give this view type a name. We recommend giving each view a unique name if you have more than one view in the table.

Click ‘**Add view’.**

![Create a personal view](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/3120675c-3c91-44f6-9436-ed566e1eb03a/Screenshot_2023-03-07_at_18.39.18.png)

## View personal views

When you open the view modal, you will see collaborative views and your own personal views by default. A personal view can only be viewed and [configured](/user-docs/view-customization) by the current owner of the view and is hidden from other workspace members by default.

![View personal views](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9f6dd870-7ad3-4684-bc8f-4c9e9ddbb0b2/Screenshot_2023-03-07_at_18.32.00.png)

## Duplicating a table containing personal views

When you [duplicate a table](/user-docs/create-a-table#duplicate-a-table) that contains personal views, those views are retained even if the member who created them is no longer in the workspace.

## Related content

  * [Create custom views of your data](/user-docs/create-custom-views-of-your-data).
  * [Collaborative views](/user-docs/collaborative-views).
  * [View configuration options](/user-docs/view-customization).

