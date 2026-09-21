# AI providers

An AI provider is one connection to an AI service, plus the list of models you want
to use from it. Baserow uses those models for AI fields, AI formula suggestions, AI
Agent actions in the Application Builder and Automations, and the Kuma assistant.

## Where to configure them

Instance staff configure shared providers in **Admin → AI providers**. Workspace
administrators configure their own in **Settings → AI providers**.

Each level allows one provider per type: one OpenAI, one Anthropic, and so on.

For every model you add, choose which features may use it under **Available for**,
and use **Test model** before selecting it anywhere. A model that is not available
for a feature does not appear in that feature's model list.

Kuma is the exception: it also needs an explicit model choice under **AI features**.
See [AI assistant configuration](ai-assistant.md).

## How instance and workspace providers combine

A workspace sees its own models first, and inherits the instance models on top:

- A workspace model replaces an instance model with the **same name**.
- Instance models the workspace has not redefined stay available.
- A workspace can switch off an inherited instance provider completely. Its own
  models then stand alone, and turning the switch back on restores inheritance.
- Disabling a model hides it from every feature in that scope.

If a workspace configures its own provider because it wants to use its own account,
switch off the inherited instance provider of the same type. Otherwise that workspace
can still use models that bill to the instance account.

Upgrading from environment-based settings does this for you: any workspace whose
settings were imported is switched off from the matching instance provider, because
its own settings replaced the instance ones before the upgrade.

## Environment variables

The `BASEROW_*` provider connection and model-list variables are **deprecated**. See
the [configuration reference](configuration.md#generative-ai-configuration) for the
full list.

They still work, with one rule: once a provider of that type is configured in the
database, its environment variables are ignored. A provider in **Admin → AI providers**
replaces them everywhere; a provider in a workspace's own **Settings → AI providers**
replaces them for that workspace. A provider type configured in neither place still
falls back to its environment settings.

Upgrading imports the variables once into **Admin → AI providers**, and workspace
settings into each workspace. After that, **editing the variables changes nothing** —
rotate credentials in the admin instead. Keep the variables until you have checked
the imported configuration; removing them early leaves you no way back.

Bedrock and Vertex AI authenticate through the provider's own SDK and have no
database equivalent, so keep using their environment configuration.

Three combinations behave differently than they did before database providers
existed. A workspace with a credential but **no models** gets no models, instead of
the environment's list. A workspace with models but **no credential** is ignored, so
it gets the environment's full list instead of its own shorter one. A workspace with
a credential but **no endpoint** uses the provider's default endpoint, rather than the
instance's `BASEROW_OPENAI_BASE_URL`. Complete the configuration in
**Settings → AI providers** to fix any of them.

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
