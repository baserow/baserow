# Baserow Documentation

Source: https://baserow.io/user-docs/row-coloring

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Row coloring

> This action is restricted to [Premium accounts](/user-docs/pricing-plans) to allow collaborators to color-code rows.

Using row coloring, you can apply colors to the rows in a grid view. You can also use row outlines to create contrasts among rows. Row colors and outlines are particularly useful when you want to look for patterns within a single view.

Since row coloring is implemented at the view level, each view can have a different configuration without affecting other views. You can apply row coloring to grid views, gallery views and kanban views.

![Row coloring](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-30_at_16.17.35.png)

You can colour your rows based on two values:

  * Single select: The only work for a [single select field](/user-docs/single-select-field)
  * Conditions: This value works on any field depending on the condition you want to use

You can automatically colour rows using custom filtering conditions, or you can add colour to rows by matching the colour of the row to the colour of an associated [single select field](/user-docs/single-select-field).

## Add a color

To add a color,

  1. Click ’**Color’** option in the view bar at the top of your table.
  2. Select the decorator type to colour your rows by 
     1. Left Border - to color the left border of a row. Colors appear as color flags on the left side of the primary field of a grid view or on the left side of the kanban and gallery card.
     2. Background colour - Row coloring applies color to the entire row
  3. Define the value you want to color the left border by 
     1. Single select: Select this option if you want to color rows the same as a single select value
     2. Conditions: Select this option if you want to color rows when they match the conditions

Note that you can only have one decorator of a type for a specific view.

![Row coloring by single select field](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/b5d4de8a2991e78ad9ec869a5a909ab5ad516df4.webp)

### Row coloring by single select field

You can colour the row cards in your view depending on the [single select field](/user-docs/single-select-field) that was used to build the card. This is especially useful if you need to quickly identify which cards came from specific fields, such as when tracking task progress.

If you choose a single select field option, select a single select field within your Grid that should the row be colored by. If your table does not have an existing single select field, you will be prompted to create one.

If there is more than one single select option, choose the desired field using the radio buttons. You can also add a new single select field and options to your table.

![Add a row color in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/a7e76dbc-a82d-4937-9207-5c85330e68d8/New%20colors.png)

### Row coloring by conditions

You can set rules by coloring records depending on conditions, and any record that satisfies those rules will instantly take on the assigned color. This is similar to [creating conditions for filtering rows](/user-docs/view-customization).

If you choose a field and condition, add color and condition to define which fields are colored and what color is used.

Add conditions by clicking on the ‘**Add condition** ’ button or ‘**\+ add color’** to apply a color by default.

![Row coloring by conditions](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/68ab149b8ea8f1cfbaf0f8992221a7ea887154d8.webp)

When a color is set, the color button will be highlighted and the number of colors stated.

## Change Row coloring

To change a row color value,

  1. Click ’**Color’** at the top right of your table.
  2. Select the specific decorator you want to delete, e.g. Left border or Background color
  3. Click the dropdown menu to select a new value, e.g. Single select or Conditions
  4. Configure the new value selected

![Change Row coloring](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-16_at_07.34.30.png)

You can also change the value of each color modification.

## Delete Row coloring

To delete a row color modification,

  1. Click ’**Color’** at the top right of your table.
  2. Select the specific decorator you want to delete, e.g. Left border or Background color
  3. Click the **delete** icon next to the color specification.

![Delete Row coloring](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-16_at_07.31.23.png)

