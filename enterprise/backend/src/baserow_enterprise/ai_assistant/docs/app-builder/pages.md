# Baserow Documentation

Source: https://baserow.io/user-docs/pages-in-the-application-builder

---


## Overview

After you’ve created an application, you can find its pages listed on the left sidebar. You can create new pages and manage all existing ones right from the sidebar in Baserow.

A page in an application has its unique set of settings that can be configured for each page separately, including [Name, Path, and Path parameters](/user-docs/application-builder-page-settings).

Each page has a three-dot icon `⋮` on it, which opens a menu with the options to rename, duplicate, and delete the page.

## Create a page

In Baserow, you have the flexibility to create a new, blank page and add [elements](/user-docs/elements-overview) to suit your needs.

When you create a new application, the application will have a Homepage by default. To expand an application’s functionality, add additional pages.

There are ways to add a new page to an application:

  * Start with a new page
  * Duplicate an existing page

### Start with a new page

In this section, we will walk you through the process of adding a page to an application.

  1. Within the application in the sidebar, click **\+ Create page**.
  2. Input a name for the new page. When you create a new page, you should give it a distinctive name that’s not the same as any other page name in the current application.
  3. Select **Start with a new page**.
  4. Click **Add page**.

When you create a new page, it’s like starting with a blank canvas. You have access to various elements you can add to this blank page. These elements help you organize and present information effectively.

![Start with a new page](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7b32e88c-6131-4bb6-b03e-c626b772c0ba/Untitled.png)

### Duplicate a page

Duplicating a page is a quick and easy way to make a copy of an existing page. This can be helpful if you need to make changes to the data without affecting the original page.

To duplicate a page in Baserow, follow these steps:

  1. In the sidebar, hover over the page you want to duplicate. You will see a small vertical ellipsis `⋮` (three dots) appear on the page.
  2. Click the three-dot icon `⋮` to open the page options menu.
  3. From the menu, select **Duplicate**.

Baserow will create a copy of the page and place it immediately below the original page. You can view the application and page duplication progress in the left sidebar.

### Customize a duplicated page

After duplicating a page in Baserow, you’ll likely want to customize the duplicated page to fit your needs.

Here are some ways you can customize duplicated pages:

  * [Modify the values of specific elements](/user-docs/elements-overview): Click on an element within the duplicated page and change its value to the desired value.
  * [Delete unnecessary elements](/user-docs/add-and-remove-elements): If the duplicated page contains elements that are not relevant, you can remove the element.
  * [Reorder elements](/user-docs/elements-overview): Click and drag an element to a different position within the page to rearrange the element order.

## Rename a page

Each page is assigned a unique name when created, but you can edit that.

  1. Locate the page you want to rename.
  2. Click the **Rename** option next to the page name.
  3. Once you’ve entered the new name, save the changes or confirm the edit according to the instructions provided.
  4. Verify that the page now displays the updated name in the dashboard.

Within the page settings, you can also find the option to change the page name. Click on the field containing the current page name and add a desired new name.

![Rename page in page settings](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/f494fc54-f994-466f-b486-29aeedbd7e50/Untitled%201.png)

## See what a page looks like to users

You can view a page as an authenticated user and evaluate the user experience from the perspective of an end-users.

By default, when you visit the editor, you’re viewing as an anonymous user.

![See what a page looks like to users](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/4726ef47-d1b8-442d-9623-17a1c46f3e35/Untitled%202.png)

To view a page as an authenticated user, follow these steps:

  1. **[Create user sources](/user-docs/user-sources)** : Ensure you have configured user sources and defined authentication methods like email/password.
  2. **[Create data sources](/user-docs/data-sources)** : Data sources allow you to display data to users or collect some data from them instead.
  3. **Access the page** : Once logged in, navigate to the page you want to view as an authenticated user. You should be able to access any page that requires authentication based on user role and permissions.
  4. **Simulate user experience** : Explore the page and interact with its features as an authenticated user would. Test functionalities such as accessing restricted content, submitting forms, or viewing personalized data based on the user’s profile.
  5. **Verify user experience** : Ensure that the page behaves as expected for authenticated users. Check for any errors, discrepancies, or unauthorized access to content that may indicate issues with the authentication setup or page configuration.

## Delete a page

To delete a page from an application, use the **Delete** option within the application’s management interface.

This action removes the selected page from the application without any additional steps or warning prompts.

## Page settings

You can access the page settings by opening the page. On the left-hand side of the top navigation bar, you can access [Elements](/user-docs/elements-overview), [Data](/user-docs/data-sources), and [Page settings](/user-docs/application-builder-page-settings).

Learn more about the [page settings](/user-docs/application-builder-page-settings).

