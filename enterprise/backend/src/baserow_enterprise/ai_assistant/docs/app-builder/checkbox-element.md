# Baserow Documentation

Source: https://baserow.io/user-docs/application-builder-checkbox-element

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Application Builder - Checkbox element

The checkbox is a handy tool for users to quickly say yes with a tick or no by leaving it blank.

Let’s go over how to set up a checkbox and talk about each setting option.

## Overview

A checkbox is a little box you can check or leave empty. For the checkbox element, you can configure the element properties and [style](/user-docs/element-style) from the element settings.

It’s commonly used to give a choice between two options, typically ‘true’ or ‘false.’ When you check the box, it means ‘true,’ and when you leave it unchecked, it means ‘false.’ It’s a way to select one or more options from a list by clicking on them.

Learn more about the [boolean field in the Baserow table](/user-docs/boolean-field).

The Application Builder allows you to bind the text to [data sources](/user-docs/data-sources). This enables the text to update dynamically based on user input or application logic.

![Application Builder - Checkbox element](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9b1b27c2-05c0-4cec-b863-afea7b4ee2b9/Untitled.png)

## Add and configure checkbox elements

To add a checkbox element, access the [elements panel](/user-docs/elements-overview) and select **Checkbox**.

Once added, place the checkbox wherever you want it on the [page](/user-docs/pages-in-the-application-builder). Don’t worry if it’s not perfectly positioned initially; you can always move it later.

Learn more about how to [add and remove an element from a page](/user-docs/add-and-remove-elements).

![Add and configure table elements](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/4281431d-3a77-448c-b627-1a7426a088b6/Untitled%201.png)

Now, you’ll configure the checkbox’s properties to make it function and look the way you want. This involves settings related to checkbox style.

## Configure checkbox element

When setting it up, you’ll have some configuration options, like deciding what each choice represents or customizing its appearance. It’s like tailoring the checkbox to fit your specific needs.

The checkbox element has the following common settings:

  * **Label** : The label provides context for what the checkbox represents. This is the text that appears next to the checkbox, indicating what the checkbox is for. It should be clear and concise, explaining the purpose of selecting or deselecting the checkbox.

  * **Default value** : The default value sets the initial state of the checkbox. This refers to the state of the checkbox when the form loads. For a yes/no checkbox, the default value could be either “Yes” (checked) or “No” (unchecked), depending on the context and the expected user behavior.

  * **Required** : This option determines whether the user must interact with the checkbox before submitting the form. If the checkbox is required, the user must check yes before proceeding. If it’s not required, the user can choose to leave the checkbox unchecked.

