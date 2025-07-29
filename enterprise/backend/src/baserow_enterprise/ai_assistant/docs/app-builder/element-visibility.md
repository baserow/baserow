# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-element-visibility

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Element visibility

The visibility tab provides a powerful tool to control access to information and functionalities within your application.

This article explains how to control who sees specific [elements](/user-docs/elements-overview) within your application using the visibility tab in the Application Builder.

> Learn more about [page visibility](/user-docs/application-builder-page-settings#page-visibility) to control which user groups can see specific pages in your application.

## Overview

The visibility tab allows you to define which user groups can view specific elements in your application according to a [user’s authentication status](/user-docs/user-sources). This is helpful for situations where you want to:

  * Restrict access to certain content for logged-in users only.
  * Provide special information for visitors who haven’t signed up yet.
  * Control what everyone, regardless of login status, can see.

You can set a different visibility level for each element in your application. This allows you to create a customized user experience based on login status.

![Baserow Visibility tab and its location on the right-side panel](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d809d3da-d097-446a-be89-ce891dfd8fe8/Baserow%20Visibility%20tab%20and%20its%20location%20on%20the%20right-side%20panel.png)

## How to use the visibility tab

  1. **Select an Element:** Click on the element in your application that you want to control visibility for. This could be a button, text, image, or any other element.
  2. **Open the visibility tab:** Look for the right-side panel within the Application Builder. There should be a tab labeled “Visibility”.
  3. **Choose visibility level:** Within the Visibility tab, you’ll see three options: 
     * **All visitors:** This option makes the element visible to everyone who visits your application, regardless of their login status.
     * **[Logged-in visitors](/user-docs/application-builder-login-element):** This option restricts the element to users who have successfully logged in to your application.
     * **Logged-out visitors:** This option makes the element visible only to users who haven’t logged in yet.
  4. **Set visibility:** Click on the desired option to define who can see the selected element.

## Set visibility roles for logged-in visitors

![Visibility roles for Application Builder ](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d4df6672-9e82-4c87-ba65-0bf8d8b516a5/Visibility%20roles%20for%20Application%20Builder%20.png)

Visibility roles provide a granular level of control over user access. By defining roles within your application and assigning them to users, you can determine which elements each user can see.

Before using visibility roles, you’ll need to establish the different user roles within your application.

  1. [Create a field in the table](/user-docs/adding-a-field) to store the assigned role for each user based on their permissions.

  2. In the Application Builder, navigate to your [User Source](/user-docs/user-sources) settings. There, you’ll define a role field. This field will be used to map user data in your [User Source](/user-docs/user-sources) to the roles you established. or use the default role to assign appropriate roles to each user.

  3. Navigate to the element’s Visibility tab within the editor. This allows you to define visibility based on user roles:

     * **All roles** : This option makes the element visible to all users, regardless of their role.
     * **Allow roles** : Choose this option to define which specific user roles can see the element. Only users assigned to the selected roles will have access.
     * **Disallow roles** : This option hides the element from users assigned to the selected roles. All other users will still see the element.

This empowers you to create custom user experiences tailored to different user types.

## Note: Visibility security

> We’re constantly enhancing the security features of the Application Builder.

Elements that are hidden on the frontend are also secured on the backend so that data from those elements are never returned by the underlying API if the authenticated user does not have access.

Here’s how the data security works:

  1. If you create an element (like a table or form) that shows certain data from a data source, and make that element visible to a specific user role, then users with that role can access only that specific data they can see.
  2. Similarly, if you create an action button that lets users update certain fields, they can only update exactly what that button is configured to change - nothing more.

For example:

  * If you make a table element visible to the “Sales” role that shows customer names and order totals, users with the Sales role can only see those two pieces of information and nothing more and the API will only return the necessary data.
  * If you add an “Update Status” button visible to “Support” role, they can only update the status field, even if they can see other fields.

In a nutshell, securing the API is inherent to how you design your application — by controlling what data is available to users, you define what the API exposes.

