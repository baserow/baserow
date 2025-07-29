# Baserow Documentation

Source: https://baserow.io/user-docs/multiple-select-field

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Multiple select field

Similar to a [single select field](/user-docs/single-select-field), a multiple select field lets you choose from a list of predefined options. However, unlike a single select field, you can choose as many options as you want for each cell. This doesn’t create two fields, but rather a field with two entries in it.

## Add a multiple select field

To create a single select field, add a new field with the + button and select the Multiple select type from the dropdown menu.

An autocomplete menu will appear when you edit a cell in a multiple select field. You can input to limit the list of alternatives or choose the desired option from the dropdown menu.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/1092a3e2-aeab-4478-bc25-f09247fd2efa/Screenshot_2022-07-14_at_09.23.34.png)

A small token representing each choice option is shown and can be removed from the row by clicking the `x`.

## Set a default value

You can set a default value for multi select fields that will automatically be applied to new rows. When you set a default option, any new row created in the table will have this value pre-selected in the single select field.

To set a default value:

  1. Click on the dropdown beside the field to reveal the field configuration menu and select **Edit field**
  2. In the field configuration dialog, locate the **Default value** section
  3. Select the option you want to use as the default from the dropdown menu
  4. Click **Save** to apply the changes

## Customize multiple select options

In the multiple select field customization menu, you can add, remove, reorder and update a selection of choices.

A multiple-select field can save time when edits need to be made. For example, if you have a multiple select field that contains ‘red’, ‘blue’ and ‘yellow’ but decide that ‘yellow’ should really need to be ‘green’, you only need to change this once. As soon as the change has been made, all the records that reference ‘yellow’ will be changed to ‘green’. You don’t need to re-enter the values yourself. This can save you lots of time, especially if you’ve already got hundreds of records with ‘yellow’ as a value in the field.

### Add a multiple select option

To create a new multiple select option,

  1. Click on the dropdown beside the field to reveal the field configuration menu and select **Edit field**.
  2. Add a new option with the **\+ Add an option** button.
  3. Click on the **Change**.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/ca98df48-be84-4b27-a98e-b557e6d4172a/Screenshot_2022-07-14_at_09.27.15.png)

Alternatively, add new select options on the fly as you’re filling out the cells without going to the field configuration menu. You can create a new select option by typing in the name of the option you’d like to create and selecting the ‘**\+ Create new option** ’ button. New multiple select fields will be added automatically whenever a new, unique value is entered in the designated field.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/6f17590f-a805-40b1-ae1c-286ddc74a4f2/Screenshot_2022-07-14_at_09.29.35.png)

### Reorder the multiple select options

You can also reorder the select options by clicking and dragging on the reorder icons, which appear on the left-hand side of each select option.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/4e0af774-14da-4eb8-935e-09bdd3ac4abb/Screenshot_2022-07-14_at_09.30.48.png)

### Delete a multiple select option

You can also delete a select option by clicking on the `x` icon, which appears on the right-hand side of each select option. Note that when you delete a select option, the option will be removed from any cell configured.

### Modify multiple select colors

You have a choice of 15 different colours for your select options.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/00fb0a9d-ef99-4cfc-96c3-d434bcd84c31/Screenshot_2022-07-14_at_09.33.23.png)

If you want to limit the information related to each select option, consider converting the multiple select field into a [single select field](/user-docs/single-select-field).

