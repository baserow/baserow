# Baserow Documentation

Source: https://baserow.io/user-docs/generate-formulas-with-baserow-ai

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Generate formulas with Baserow AI

Using AI can save significant time previously spent crafting formulas manually. This section details how to use Baserow’s AI capabilities to automate formula creation directly within your Baserow workspace.

> Baserow AI features are available to those on the Premium plan or higher.

![Generate formula with AI baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d4d75565-b60f-48ca-81d2-197ea7c91fde/generate%20formulas%20with%20AI.png)

## Overview

The AI-powered formula generator simplifies the process of creating formulas by understanding your desired outcome in plain English. This helps with tasks like:

  * Managing project progress and deadlines
  * Calculating costs and budgets
  * Creating complex formulas based on date and time values

Baserow Cloud supports the GPT-3.5 model, which is freely available without usage restrictions. For Baserow Self-Hosted or those wishing to use a different model, use this [guide on configuring the OpenAI API key](/user-docs/ai-field#configure-api-keys).

## Using the AI formula generator

  1. Create a [formula field](/user-docs/formula-field-overview): In your table, add a new field and select the “Formula” field type.
  2. Generate formula using AI: Within the formula editor, locate the “Generate using AI” option. Click on this button to open a dedicated modal window.
  3. Choose an AI model: We suggest using high-parameter models like GPT-4 or llama3-70b for optimal performance.
  4. Describe your desired action: In the modal window, write a clear and concise prompt describing the action you want the formula to perform. Be as specific as possible to ensure accurate results.
  5. Generate formula: Once your prompt is ready, click the “Generate” button. Baserow will process your request and display a formula within a few seconds.
  6. Review and create: Carefully review the generated formula. If it meets your needs, click the “Create” button to finalize and implement the formula in your workspace.

## Related content

  * [Understand Baserow formulas and how to use formulas](/docs/tutorials/understanding-baserow-formulas).
  * [Formula field reference](/user-docs/understanding-formulas).
  * [Technical understanding of how Baserow formulas are implemented](/docs/technical/formula-technical-guide).
  * [How to use AI to generate formulas in Baserow](/blog/use-ai-generate-formulas-baserow)
  * [How to enable and configure the AI field in Baserow](/blog/configure-ai-field-in-baserow)

