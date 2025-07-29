# Baserow Documentation

Source: https://baserow.io/user-docs/ai-field

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# AI field

The AI field type allows you to add AI models directly within Baserow. The AI field can be used to generate creative briefs, summarize information, and more.

## Overview

The AI field type is only available with the Premium plan or higher. The GPT-3.5 model is currently available for free with no usage limitations.

  * **Baserow Cloud ([baserow.io](/)):** Baserow cloud supports the GPT-3.5 model, available free of charge and without usage limitations.
  * **Baserow Self-Hosted:** You are required to add your OpenAI API key to use the AI field type. API keys are configured at the workspace or instance level.

## Configure API keys

You can bring your own OpenAI API key to use a different model.

### Configure API keys at instance level

If you are using Baserow self-hosted, you can configure API keys at the instance level via [environment variables](/docs/installation%2Fconfiguration#generative-ai-configuration).

### Configure API keys at workspace level

To configure the API keys at the workspace level, go to [workspace settings](/user-docs/setting-up-a-workspace) → Generative AI. The settings apply to all users in the workspace. With the modal, you can configure generative AI at the workspace level.

The AI field may be disabled if an API key for a supported model is missing. To activate these features, [specify the settings](/user-docs/ai-field#supported-models). The configuration at the global instance level will be used by default if you leave a value blank.

![Baserow AI field](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/11dc38d8-051a-481a-86b1-38f3c0c7484f/ai_field_improvements.webp)

## Supported models

### OpenAI

To configure OpenAI, provide

  * an [OpenAI API key](https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key) to allow using OpenAI for the generative AI features like the AI field.
  * an OpenAI organization name that will be used when making an API connection (optional).
  * a comma-separated list of [OpenAI models](https://platform.openai.com/docs/models/overview) that you would like to enable (e.g. gpt-3.5-turbo,gpt-4-turbo-preview). Note that this only works if an OpenAI API key is set. If this variable is not provided, the user won’t be able to choose a model.

![Tutorial on how to use the AI field](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d9a7a43a-4f4b-4d5d-8231-78f9064f63ea/AI%20Field.png)

### Ollama

To configure Ollama, provide

  * an [OLLAMA](https://ollama.com/) host to allow using OLLAMA for generative AI features like the AI field.
  * a comma-separated list of [Ollama models](https://ollama.com/library) that you would like to enable (e.g. llama2). Note that this only works if an Ollama host is set. If this variable is not provided, the user won’t be able to choose a model.

### Anthropic

Provide an [Anthropic API key](https://docs.anthropic.com/en/api/getting-started) to allow using Anthropic for the generative AI features like the AI field.

Provide a [comma-separated list of Anthropic models](https://docs.anthropic.com/en/docs/about-claude/models) that you would like to enable in the instance (e.g. claude-3-5-sonnet-20241022,claude-3-opus-20240229). Note that this only works if an Anthropic API key is set. If this variable is not provided, the user won’t be able to choose a model.

### Mistral

Provide a [Mistral API key](https://docs.mistral.ai/getting-started/quickstart/) to allow using Mistral for the generative AI features like the AI field.

Provide a [comma-separated list of Mistral models](https://docs.mistral.ai/getting-started/models/models_overview/) that you would like to enable in the instance (e.g. mistral-large-latest,mistral-small-latest). Note that this only works if an Mistral API key is set. If this variable is not provided, the user won’t be able to choose a model.

## Create an AI field

To create an AI field in a table,

  1. Click **\+ Add a field**. Choose the **AI field** from the options.
  2. Select an AI type and model from the list.
  3. Temperature setting option: Fine-tune the creativity of AI-generated content with the temperature setting. The temperature of an LLM, a parameter set between 0 and 2, adjusts response randomness-lower values yield focused answers, while higher values increase creativity.
  4. Choices output type for classification: Select your desired output format to guide the LLM in generating responses that match your desired options. You can, for example, use this to classify whether a review positive, neutral, or negative, or classify issue types based on their descriptions.
  5. Click on the **Prompt** field in the context menu. A new window will appear with a list of fields in your table. As you type your prompt, select the fields you want to use for your result.
  6. Click the **Create field** button.

Each cell in the field will have a **Generate** button. Click the button where you want the AI to start generating prompts.

![AI field type](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e34d40cf-315a-4c21-8a76-81432c96fc41/AI%20Field.png)

## File field support for the AI field

Baserow AI allows you to use various [file formats](/user-docs/file-field) directly within the AI field. You can connect your [files](/user-docs/file-field) to the AI model and instruct it on how to process the information for data classification, text generation, content summarization, information retrieval, and similar functionalities.

Baserow AI supports a wide range of [file types](/user-docs/file-field), allowing you to work with documents, invoices, and various other formats. For a specific list of supported file types, please refer to Baserow’s documentation on [the file field](/user-docs/file-field).

![File field support for the AI field](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/e9472557-303b-4107-a77e-bc14a622b0d7/File%20field%20support%20for%20the%20AI%20field.png)

To be considered a valid knowledge base, the file must be in one of the following text-based formats:

  * .txt (plain text)
  * .md (Markdown)
  * .pdf (Portable Document Format)
  * .docx (Microsoft Word Document)

To leverage Baserow’s AI file support to gain insights directly from your documents, invoices, and other file types:

  * Select AI type and model: Choose the desired AI type and model from the available options.
  * Connect a file field: In the File field section, connect with a [file field](/user-docs/file-field) containing the documents you want to analyze. The AI will use the first compatible file in your selected file field as the source for the prompt. Ensure this file is supported.
  * Define the prompt: Here, you can specify how you want the AI to process the connected file.
  * Create the AI Field: Click the **Create field** button to finalize the configuration.
  * Generate results: Each row within your table will now display a "Generate" button. Click this button on the specific row where you want the AI to initiate processing based on your defined prompt.

