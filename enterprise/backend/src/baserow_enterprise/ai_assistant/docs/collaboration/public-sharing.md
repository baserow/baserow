# Baserow Documentation

Source: https://baserow.io/user-docs/public-sharing

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Public sharing

Sharing a specific view from a table is useful for collaborating with people outside your organization who only need access to a few items in your database.

Anyone with the link will have view-only access to the table that has been shared. You can share a table with anyone, whether or not they are a collaborator in your workspace.

An example of someone you might grant link access to is a client. For example, you are working with multiple clients on a project and want them to get a detailed view of the data.

You can hide fields from viewers. A client, for example, needs to keep track of the tasks in their project. You’ve included the category, project lead, project team, kick-off date, due date and budget. You can conceal the fields you don’t want the client to view.

If you change the visible fields in a view, the view share link will immediately reflect those changes in real-time.

## Create a private shareable link to the view

A shared view allows anyone to see the data in any table in your database.

To publicly share a view:

  1. Visit a grid or form view on any table.
  2. Click the **Share view** option of the supported view you want to share.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-15_at_19.52.43.png)

  3. Share the view using the link or the **Copy link** icon. You can also customize the view using the options that appear:

     * **Restrict access with a password** : The public link will only be accessible after entering the password. This password will be saved encrypted. A minimum of 8 characters is required here.
     * **Disable shared link** : The password will be deleted and it will not be possible to recover it.
     * **Generate new URL:** To automatically expire the old link shared, create a new publicly shared URL.
     * **Change password** : By changing the password, the previous one will no longer work. This password will be saved encrypted.

![publicly share a view in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-17_at_13.52.07.png)

  4. Preview the view share link (copy URL)

## Footer aggregation

Grid View footer aggregations are summary calculations displayed at the bottom of a data table. These calculations can provide valuable insights into your data by summarizing specific fields. For example, a footer aggregation can display the total sum or average of a particular field.

When you share a [grid view](/user-docs/guide-to-grid-view) publicly (meaning anyone can access it), any footer aggregations you’ve set will also be visible to your viewers. This allows you to showcase additional data insights alongside the information in the [grid view.](/user-docs/guide-to-grid-view)

> Learn more about [footer aggregations](/user-docs/footer-aggregation).

![Footer aggregation in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/0b8b0af7-7253-481a-a6e9-5aff6446afc9/footer%20aggregations%20in%20public%20grid%20views.png)

## Share form

Anyone, including Members, can share a form. To share the link with anyone when you’re done creating your form, click on ‘**Share form** ’ at the top of the screen and proceed to create a private shareable link to the form.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-09_at_13.04.45.png)

After you create a private shareable link to the form, you will find the **link settings** in the ‘Share form’ pop-up of your form.

Copy and paste the link to easily share your forms with anyone.

### Generate a new share link URL

If you want to restrict existing access to a form, you can refresh the URL. By selecting the refresh button next to the URL, you can generate a new form link. This disables the current form share link.

After refreshing, a new URL will be generated and it will not be possible to access the form via the old URL. Everyone that you have shared the URL will not be able to access the form.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-09_at_13.05.36.png)

### Restrict view access with a password

This keeps the share link active for respondents who have a password. Click the **Restrict access with a password** toggle to switch it on or off. The public link will only be accessible after entering the password. This password will be saved encrypted. A minimum of 8 characters is required.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-29_at_00.50.41.png)

### Disable shared link

You can disable the link to stop accepting new form submissions. To stop sharing the form, click on the Share form button and then the **x disable shared link** to turn off sharing immediately. This disables the form. If you later want to open the form again, simply create a private shareable link.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-29_at_00.49.49.png)

## Hide/show fields

View share links don’t display hidden fields in the shared view, even if you [enlarge a row](/user-docs/navigating-row-configurations) in the view share link.

Only fields that are not hidden will be visible in publicly shared views. Choose what information is shared publicly by using the **Hide fields** option.

Fields are hidden even when records are expanded in the view share link. Learn more about the basics of [hide and show fields](/user-docs/field-customization).

## Filter and sort from a view share link

You can create multiple views with different filters and easily share your data by creating a public link.

If you create a view share link, the sorting conditions used to create the view will be available to others who access the view through the link. Viewers will be able to sort and filter data in any way they like

However, sort options set in a view you share via a view share link do not affect how that view displays data in the table itself.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-30_at_16.51.20.png)

## Embed a view via iframe tag

To embed a view via an iframe. Share a grid view publicly, copy the publicly shared URL and replace `YOUR_URL` in the code snippet below:
    
    
    <iframe src="YOUR_URL" frameborder="0" width="100%" height="400"></iframe>
    

## Hide Baserow logo

You can remove the Baserow logo from your public view.

> Upgrade to the premium version to use the public logo removal. You can upgrade your account by getting a license. For more details about Baserow subscriptions, [visit this article](/user-docs/subscriptions-overview).

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d8f82e8f-90b9-4004-8907-1946e6e63889/Screenshot%202022-11-08%20at%2014.26.45.png)

You can [create multiple views](/user-docs/create-custom-views-of-your-data) with different filters and easily share your data by creating a public link.

## Related content

  * [View configuration options](/user-docs/view-customization).
  * [Work with gallery views](/user-docs/guide-to-gallery-view).
  * [Work with grid views](/user-docs/guide-to-grid-view).
  * [Work with kanban views](/user-docs/guide-to-kanban-view).
  * [Work with calendar views](/user-docs/guide-to-calendar-view).

