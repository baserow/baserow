# Create a template

Templates are a starting point for other users. They can use them for inspiration and
easily install them into their workspaces. A template consists of one or more applications
that will be copied into the desired workspace if a user decides to install it. It is also
possible for the user to see an preview of the template before installing.

## Build your own

If you want to create your own template, you first need to make one in an installation
of Baserow. You need at least version 1.1 because that contains the exporting
functionality that you are going to need later.

The first step is creating a new empty workspace. It doesn't matter what it is named. Next
you can create the applications that you want to have in your template in the workspace
you just created.

If you for example want to create a content calendar, you might want to create a
database named `Content Calendar` that contains three tables names `Pipeline`,
`Campaigns` and `Authors`. Once you have filled in all the tables in the way you want,
you can proceed to the next step, which is exporting the workspace you just made to then
create a template based off it.

## Exporting the applications

It is possible to make an export of all the applications that are in a workspace. When a
user installs a template, then that export is used to import the applications
into the user's desired workspace. It is only possible to make this export via the command
line interface of Baserow.

Before you can export the application, you first need to figure out what the ID of your
workspace is. You will see a list of all your workspaces when you click on the name of your
workspace in the sidebar. If you hover over a workspace there, you will see the click-able
three dots. If you click on that you will see another context menu containing the name
of that workspace, and a number between brackets. That number is your workspace ID.

Now that you have the workspace ID that contains your template, you need to export it to
JSON format. In order to do that you need access to the command line of your Baserow
environment. This could be different depending on how your environment is installed.
A couple of examples:

### Development environment

Inside the backend container you need to execute the following command:

```
$ python src/baserow/manage.py export_workspace_applications YOUR_WORKSPACE_ID --indent
```

### Cloudron environment

By logging into your Cloudron environment, you can access to the terminal of your
Baserow app. There you can enter the following command to export your application:

```
$ /app/code/env/bin/python /app/code/baserow/backend/src/baserow/manage.py export_workspace_applications YOUR_WORKSPACE_ID --indent --settings=cloudron.settings
```

### Ubuntu environment

Connect to your server via SSH and execute the following commands:

```
$ cd /baserow
$ source backend/env/bin/activate
$ export DJANGO_SETTINGS_MODULE='baserow.config.settings.base'
$ export DATABASE_PASSWORD='yourpassword'
$ export DATABASE_HOST='localhost'
$ baserow export_workspace_applications YOUR_WORKSPACE_ID --indent
```

### The export

After running the management command, you will notice that two files have created in
your working directory, `workspace_YOUR_WORKSPACE_ID.json` and `workspace_YOUR_WORKSPACE_ID.zip`. The
JSON file contains the structure of your export, which are the databases, tables,
fields, views and rows. The ZIP file has all uploaded files related to the exported
applications. A file could for example be included in the ZIP file if a table contains
a file field and files have been uploaded.

## Creating the template file

Inside the `backend/templates` directory you will find all the existing templates. You
need to create a new JSON file here that has the same content as shown below. You can
replace the values with something that matches your template. We keep all the templates
as JSON files so that everyone who self hosts also has access them.

-   **name**: The name of the template that is visible to the user.
-   **description**: One sentence about what the template helps with, shown on the
    template card and in its details panel. Changing only the description doesn't
    reinstall the template.
-   **icon**: An icon class name that is visible to the user (`iconoir-{icon}` or `baserow-icon-{icon}`).
-   **keyword**: Invisible keywords will only be used to improve searching.
-   **categories**: The categories that the template belongs to.
-   **export**: The export value must contain the contents of the exported JSON file
    after running the `export_workspace_applications`. This file is named
    `workspace_YOUR_WORKSPACE_ID.json`.

```json
{
    "baserow_template_version": 1,
    "name": "Content Calendar",
    "description": "Plan, schedule and track content across channels.",
    "icon": "iconoir-user",
    "keywords": ["Example", "Template", "For", "Search"],
    "categories": ["Test category 1"],
    "export": []
}
```

The export has also generated a ZIP file containing all the related files. This file is
named `workspace_YOUR_WORKSPACE_ID.zip`. It must be placed inside the `backend/templates`
directory and should have the same name as the template JSON file. If for example the
template is called `applicant-tracker.json`, the ZIP file must be named
`applicant-tracker.zip`.

## Synchronizing the template

In order to try out your template, you need to run the `sync_templates` management
command. This will make sure that a copy of the template is added to the database so
that the user can see a quick preview.

If everything works, you could create a merge request and share your template with the
community.
