# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-file-input-element

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Application Builder - File Input element

The File Input element enables users to upload files directly through your application. This enterprise/advanced feature enhances data collection capabilities by allowing end users to submit files that can be stored in your Baserow tables.

In this section, we’ll guide you through setting up a file input element and explain each configuration option in detail.

## Overview

For the file input element, you can configure the element properties and [style](/user-docs/element-style) from the element settings panel on the right side of the screen.

The File Input element is particularly useful when combined with workflow actions to create or update rows in your database, with the uploaded files stored in “File” type fields.

## Add and configure file input elements

To add a file input element, access the [elements panel](/user-docs/elements-overview) and select **File Input**.

Once added, place the file input wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned initially; you can always move it later.

> Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

Now, you’ll customize the file input’s behavior and appearance by configuring its properties.

## File Input configuration options

### General settings

  * **Label** : Add a descriptive text that appears above the file input to guide users on what files to upload.

  * **Help text** : Provide additional context or instructions inside the button to assist users with file selection. _Leaving this empty will result in the default text Drag and drop files here or click to select_

  * **Required** : When enabled, users must upload at least one file before form submission is allowed.

  * **Multiple files?** : Enable this to allow the user to upload more than one file.

  * **Initial file URL?** : Shows an example file underneath the input.

  * **Initial file name?** : Gives the example file a title.

### File restrictions

  * **Allow multiple files** : Toggle this option to allow users to upload one or multiple files within a single file input element.

  * **Maximum files** : Define how many files users can upload (when multiple files are allowed). This setting helps prevent excessive uploads.

  * **Maximum file size** : Set the maximum allowed size for each uploaded file (in MB). This helps control storage usage and prevents extremely large file uploads.

  * **Preview images?** : Will generate a small preview of the file if it is an image file format.

## Working with uploaded files

### Using with workflow actions

The File Input element works seamlessly with workflow actions to store uploaded files in your database:

  1. **Create Row action** : Include the uploaded file in a new database record
  2. **Update Row action** : Add or replace files in an existing record
  3. **Form Submit action** : Process multiple inputs including file uploads

