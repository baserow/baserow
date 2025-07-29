# Baserow Documentation

Source: https://baserow.io/user-docs/single-select-field

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Single select field

A single select field is ideal when you only want to be able to choose one item from a predefined list of choices (e.g. a state or country).

The single select field option is where you are presented with a set of values and you can only select one from the list of preset options. A classic example could be colors like ‘Red’, ‘Blue’ and ‘Yellow’. The person entering data can then select one of these options to become the field data value.

An autocomplete menu will appear when you edit a cell in a single select field. You can start to type to limit the list of alternatives or choose the preferred option from the dropdown menu.

## Add a single select field

To create a single select field, [add a new field](/user-docs/field-customization) with the + button and select the **Single select** type from the dropdown menu.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/78a952d1-3f07-4efd-be1e-d5efb688d322/Screenshot_2022-07-14_at_08.51.51.png)

## Set a default value

You can set a default value for single select fields that will automatically be applied to new rows. When you set a default option, any new row created in the table will have this value pre-selected in the single select field.

To set a default value:

  1. Click on the dropdown beside the field to reveal the field configuration menu and select **Edit field**
  2. In the field configuration dialog, locate the **Default value** section
  3. Select the option you want to use as the default from the dropdown menu
  4. Click **Save** to apply the changes

## Customize single select options

In the single select field customization menu, you can add, remove, reorder and update a selection of choices.

A single select field can save time when edits need to be made. For example, if you have a single select field that contains ‘red’, ‘blue’ and ‘yellow’ options but decide that ‘yellow’ should really need to be ‘green’, you only need to change this once. As soon as the change has been made, all the records that reference ‘yellow’ will be changed to ‘green’. You don’t need to re-enter the values yourself. This can save you lots of time, especially if you’ve already got hundreds of records with ‘yellow’ as a value in the field.

### Add single select option

To create a new single select option,

  1. Click on the dropdown beside the field to reveal the field configuration menu and select **Edit field**.
  2. Add a new option with the **\+ Add an option** button.
  3. Click on the **Change**.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/ccc90947-b3f7-42a3-babc-a953be335ef9/Screenshot_2022-07-14_at_09.02.35.png)

Alternatively, add new select options on the fly as you’re filling out the cells without going to the field configuration menu. You can create a new select option by typing in the name of the option you’d like to create and selecting the **\+ Create new option** button. New single select fields will be added automatically whenever a new, unique value is entered in the designated field.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2dbb85c9-edae-46d0-bc40-e7a9894033db/Screenshot_2022-07-14_at_08.57.29.png)

### Reorder the single select options

You can also reorder the select options by clicking and dragging on the reorder icons, which appear on the left-hand side of each select option.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/acd7afe7-74ed-433a-b4eb-f8fd242c14a9/Screenshot_2022-07-14_at_08.54.44.png)

### Delete select option

You can also delete a select option by clicking on the `x` icon, which appears on the right-hand side of each select option. Note that when you delete a select option, any cell configured with this option will be empty and any [kanban views](/user-docs/guide-to-kanban-view) grouped by this option will be uncategorized.

### Replace a single select option

To replace a single select option, select a new option. The single select option only allows one value so selecting a new option will replace the previous option. Note that if you use this option to sort, filter or group a [kanban view](/user-docs/guide-to-kanban-view) in a table, the views will also be modified.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/1703438f-86d5-42f7-a365-513e621a9f9a/Screenshot_2022-07-14_at_09.14.46.png)

### Modify single select colors

You have a choice of 15 different colours for your select options.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/5758a766-866a-4eb0-8511-d35df8af8115/Screenshot_2022-07-14_at_09.10.09.png)

If you want to store additional information related to each select option, consider converting the single select field into a [multiple select field](/user-docs/multiple-select-field).

