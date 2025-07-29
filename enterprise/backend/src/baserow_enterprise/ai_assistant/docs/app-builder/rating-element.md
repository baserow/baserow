# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-rating-element

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Application Builder - Rating element

The Rating element allows users to display, collect, and view ratings in your application. Rating elements provide visual feedback through star, heart, or numeric representations, making them ideal for collecting user feedback or displaying evaluation scores.

In this section, we’ll guide you through setting up different rating elements and explain each configuration option in detail.

## Overview

Baserow offers three different rating element types to serve various purposes in your application:

  1. **Rating** : Shows a static rating value represented by stars, hearts, or numbers. This is useful for displaying pre-existing ratings from your data source.
  2. **Rating Input** : Allows users to provide ratings that can be stored in your database. Perfect for collecting user feedback or reviews.
  3. **Rating Column** : Integrates within table elements to display rating values alongside other data in a structured format.

For all rating element types, you can configure the element properties and [style](/user-docs/element-style) from the element settings panel.

## Add and configure rating elements

To add a rating element, access the [elements panel](/user-docs/elements-overview) and select **Rating** or **Rating input**.

Once added, place the rating element wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned initially; you can always move it later.

> Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

Now, you’ll configure the rating element’s properties to make it function and look the way you want.

## Rating element

The Rating element is perfect for showing existing ratings from your data sources. It’s a read-only element that visualizes numeric values as ratings.

### Configuration options

**Rating value** : Set the value to display. This can be:

  * A static numeric value between 0 and 10
  * A field from a connected [data source](/user-docs/data-sources)   
**Maximum rating** : Define the maximum possible rating value, which determines the number of rating symbols displayed (between 1 and 10).   
**Style** : Select the visual representation of your ratings:
  * Stars
  * Hearts
  * Thumbs up
  * Flags
  * Smiles   

  * **Symbol color** : Customize the color of filled symbols using:
  * Hexadecimal color code
  * RGB value
  * Color picker
  * Primary/Secondary/Border/Success/Warning/Error

## Rating Input element

The Rating Input element allows users to provide ratings by clicking or tapping on rating symbols. This interactive element is perfect for forms and feedback collection.

### Configuration options

In addition to the display options available in the Display Rating element, the Rating Input includes these additional settings:

  * **Label** : Add descriptive text above the rating input to guide users.

  * **Default value** : Set a pre-selected rating that appears when the page loads.

  * **Required** : When enabled, users must provide a rating before form submission.

## Rating Column in Table elements

When configuring a table element, you can display rating values as one of the column types. This integrates seamlessly with your tabular data.

### Configuration steps

  1. Add a [table element](/user-docs/application-builder-table-element) to your page
  2. In the table’s field configuration, add a new field or edit an existing one
  3. Set the field type to **Rating**
  4. Configure the value mapping to the data source field containing rating values
  5. Adjust the rating display settings to match your needs   

## Working with Rating data

  
### Connecting to data sources 

The Application Builder allows you to bind rating elements to [data sources](/user-docs/data-sources). This enables:

  * Display Rating elements to show values from your database
  * Rating Input elements to store user ratings back to your database
  * Dynamic rating displays that update when data changes

### Using Rating elements with workflows

Rating Input elements work particularly well with workflow actions:

  * Collect user feedback and store it in database tables
  * Create satisfaction surveys with multiple rating inputs
  * Update existing ratings based on user input

