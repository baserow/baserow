# Introduction

!!! danger "Legacy plugin system — no longer works"

    This describes the original Baserow plugin system from before 2.1.
    **It no longer works.** Internal APIs and registration surfaces have
    changed substantially since 2.1, and the boilerplate has not been
    updated. A plugin built against these docs will not load against
    current Baserow.

    The pages below are kept for historical reference only. To extend a
    self-hosted Baserow install today, use
    [custom client scripts](custom-client-scripts.md) — a small frontend
    extension mechanism driven by the `BASEROW_EXTRA_CLIENT_SCRIPT_URLS`
    environment variable (enterprise feature).

Baserow plugins let you fully customize and extend Baserow quickly and easily. Multiple
plugins can be installed into a new or existing Baserow installation, they get full
access to Baserow's internals for maximum customization and are straightforward develop
and publish.

Some examples of what you can do with a Baserow plugin are:

* Add new Baserow:
    * Field Types
    * View Types/Filters/Sorts/Decorations/Aggregations
    * Formula Functions/Types
* Add or customize pages, components, styling
* Integrate with 3rd party APIs or software
* Install custom postgres extensions, system packages, python and node dependencies
* And much more!

Baserow Plugins are only available for self-hosted installations currently and are 
**experimental** and subject to change.

1. **You should always make backups of your Baserow data before installing and using any
   plugin.**
2. **You should only ever install plugins from a trusted source.**
3. **Baserow is not responsible for and does not officially support any plugins
   currently, installing and using them is entirely at your own risk.**

## Installing a Plugin

The [Plugin Installation](./installation.md) guide goes into detail on how to install
and uninstall Baserow plugins in the various official Baserow docker images.

Currently, we do not provide an officially supported plugins, however check out our
[Plugin community sub-forum](https://community.baserow.io/c/plugins/17) for community
made plugins and further discussion.

## Step by step plugin creation tutorial

Check out
our [step by step tutorial on plugin creation using the plugin boilerplate](./boilerplate.md)
for a quick and easy way to get a plugin started.

## Creating a Plugin

Finally, the [Plugin Creation](./creation.md) guide explains in more detail how to
create your own plugins and publish them for others to use.

