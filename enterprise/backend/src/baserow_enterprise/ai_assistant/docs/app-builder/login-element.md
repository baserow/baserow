# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-login-element

---


## Overview

The login element is an important component for securing your application. To enable user authentication, you’ll need to choose a [user source](/user-docs/user-sources). This provides information needed to recognize and validate users attempting to log in.

## Add and configure login elements

To add a login element, access the [elements panel](/user-docs/elements-overview) and select **Login**.

Once added, place the element wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned at first; you can always move it later.

Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

![Add and configure login elements](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/4561f5d6-e1f6-4d3c-8103-7e23db516c6c/Untitled.png)

Now, you’ll customize the login’s behavior and appearance by configuring its properties. This involves settings related to login style.

## Choose a user source to use the login element

To configure the login element, you’ll first need to choose the [source of your user data](/user-docs/user-sources). This determines where the application will verify user credentials during the login process.

The user source is essentially how your application identifies and verifies users. It establishes the foundation for secure login functionality.

Adding a user source allows the application to recognize and authenticate users effectively. By adding a user source, you define how users will authenticate themselves within the application. This typically involves configuring settings related to username and password verification.

Learn more about [how to add or configure a user source](/user-docs/user-sources).

![Choose a user source to use the login element](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/c2d28ec6-d16b-49a4-9232-426d5b05c704/Untitled%201.png)

Once you’ve chosen the user source, you can establish a secure connection and enable user authentication using the chosen method.

## Using email and password for login

Baserow’s [password field type](/user-docs/password-field) provides a secure way to manage user credentials within your application. This functionality allows you to:

  * Set unique passwords for each user record.
  * Store passwords securely within your Baserow database.
  * Create new rows containing password data.

By configuring a user source that leverages email and password login, users can authenticate themselves using their existing credentials. This streamlines the login process and enhances application security.

Learn more about the [password field type](/user-docs/password-field).

![Using email and password for login](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e55f2618-ae71-4f52-b321-a7912069b0fd/Untitled%202.png)

## What happens after login?

Once a user successfully logs in with a valid username and password, you can set the visibility of each element in your application according to a user’s authentication status.

![What happens after login in Baserow?](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/6979e3f0-c9f5-4ae5-9dc7-52e1b6bbfb8f/Untitled%203.png)

You can add a [logout action](/user-docs/element-events). This can be set up as a [button element](/user-docs/application-builder-button-element), with the ‘On click’ event configured to trigger a ‘Logout’.

Clicking the logout button will end the user’s session and return them to the login screen.

![Baserow logout button will end the user's session ](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/8a1906dc-375a-4811-a222-6954cd75a7fe/logout.png)

## Troubleshooting

**When a user successfully logs in, the next action after login is not initiated**

The user may not have permissions to view the page that needs to be opened after login in.

When you configure Page Visibility on a page, but the visitor doesn’t have permissions to view that page, they will be automatically redirected to the login page.

To fix this:

  * In the Page Editor, go to the page that the “Open a Page” action is pointing to.

  * Click Page Settings -> Visibility

  * Make sure that the visibility settings are correct.

    * If the visitor’s role is not included, make sure the visibility rules allow the visitor’s role in the “Allow roles…” list.
    * If the “Allow roles” doesn’t have any roles to select, it means the user hasn’t configured the User Roles correctly.
  * To configure User Roles, go to Application settings -> Users.

    * Make sure a User Source exists
    * Make sure the Role field is selected and that it is pointing to the correct database field.
  * Check that the page uses a valid data source.

