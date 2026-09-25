# AI providers

An AI provider is one connection to an AI service, plus the list of models you want
to use from it. Baserow uses those models for AI fields, AI formula suggestions, AI
Agent actions in the Application Builder and Automations, and the Kuma assistant.

## Where to configure them

- **Instance admins**: click the workspace name at the top of the sidebar, then
  **Admin tools → AI providers**. Models added here are available to every workspace
  on the instance.
- **Workspace admins**: go to **Home**, click the workspace name at the top of the
  page, then **Settings → AI providers**. Models added here are available to that
  workspace only.

Each page allows one provider per type: one OpenAI, one Anthropic, and so on. Other
users see changes made in **Admin tools → AI providers** after they reload the page.

For every model you add, choose which features may use it under **Available for**,
and use **Test model** before selecting it anywhere. A model that is not available
for a feature does not appear in that feature's model list.

Kuma also needs a model chosen under **AI features** in **Admin tools → AI providers**.
Workspaces inherit that choice unless a workspace admin picks another model or
disables Kuma. See [AI assistant configuration](ai-assistant.md).

## Upgrading to Baserow 2.4

**From Baserow 2.4, the environment variables below are no longer read.** The upgrade
imports them once into **Admin tools → AI providers**, and each workspace's own AI
settings into that workspace's **Settings → AI providers**. Rotate keys and change
models there: changing or removing a variable has no effect.

| Provider   | Variables                                                                                                   |
| ---------- | ----------------------------------------------------------------------------------------------------------- |
| OpenAI     | `BASEROW_OPENAI_API_KEY`, `BASEROW_OPENAI_MODELS`, `BASEROW_OPENAI_ORGANIZATION`, `BASEROW_OPENAI_BASE_URL` |
| OpenRouter | `BASEROW_OPENROUTER_API_KEY`, `BASEROW_OPENROUTER_MODELS`, `BASEROW_OPENROUTER_ORGANIZATION`                |
| Anthropic  | `BASEROW_ANTHROPIC_API_KEY`, `BASEROW_ANTHROPIC_MODELS`                                                     |
| Mistral    | `BASEROW_MISTRAL_API_KEY`, `BASEROW_MISTRAL_MODELS`                                                         |
| Ollama     | `BASEROW_OLLAMA_HOST`, `BASEROW_OLLAMA_MODELS`                                                              |

Keep the variables until you have checked the imported providers, since rolling back
to 2.3 needs them. Then remove them. The imported API keys are stored in the
database, so database backups now contain them.

There are two exceptions:

- **Kuma's model is not imported.** Kuma keeps using
  `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` until you make a model available to Kuma and
  select it under **AI features**. Imported models are only available to AI fields and
  AI Agent actions. Bedrock and Vertex AI can't be added in AI providers, so keep their
  environment configuration. See [AI assistant configuration](ai-assistant.md).
- **Variables still work for a provider that isn't in AI providers**: for example one
  the upgrade skipped (the upgrade log says why), one whose variables you add after
  upgrading, or an imported provider you deleted. This fallback is deprecated: add the provider
  in **Admin tools → AI providers** instead.

If complete workspace settings are skipped because an API key or model name exceeds
the database limits, their existing connection and model list remain in use until
you create a workspace provider.

Three workspace setups behave differently after the upgrade. Fix them in the
workspace's **Settings → AI providers**:

- A workspace with a credential but **no models** now gets no models, instead of the
  instance's list.
- A workspace with models but **no credential** now gets the instance's full list,
  instead of its own shorter one.
- A workspace with a credential but **no endpoint or organization** now uses the
  provider's defaults, instead of the instance's.

## How instance and workspace providers combine

A workspace sees its own models first, and inherits the instance models on top:

- A workspace model replaces an instance model with the **same name**.
- Instance models the workspace has not redefined stay available.
- A workspace can switch off an inherited instance provider. Its own models then
  stand alone, and turning the switch back on restores inheritance.
- Disabling a model hides it from every feature in that scope.

If a workspace configures its own provider because it wants to use its own account,
switch off the inherited instance provider of the same type. Otherwise that workspace
can still use models that bill to the instance account. The switch does not affect
Kuma: it keeps using the instance's Kuma model until the workspace chooses another
model or **Disabled** under **AI features**.

The upgrade does this for you: any workspace whose settings were imported is switched
off from the matching instance provider, because its own settings replaced the
instance ones before the upgrade. An instance provider added after the upgrade is
inherited by those workspaces, so switch it off there yourself.

## AI integrations in the Builder and Automations

An AI integration normally inherits its workspace's providers. It can also carry its
own settings:

- A **complete** connection with its own model list is independent. Central
  credentials, disabled models and feature availability do not apply to it.
- A connection **without** a model list inherits which models are allowed.
- An **incomplete** connection cannot borrow a credential from anywhere else. It can
  only narrow the inherited model list, and its connection fields are ignored.

## Published applications

An application published **before** the upgrade kept a copy of the workspace settings
that were in force at publish time, so rotating a credential centrally does not reach
it. Applications published since resolve their workspace's providers when they run, so
they follow central changes.

Either way, an integration that carries its own complete connection keeps using it.
Republishing adopts current workspace resolution — and also publishes every other
pending draft change, so confirm the draft with the application owner first.
