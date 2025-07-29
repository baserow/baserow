# Baserow Documentation

Source: https://baserow.io/user-docs/set-up-baserow

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Set up Baserow version

In this article, we’ll cover how to set up Baserow and get the most out of it.

There are two ways to use Baserow:

  * Baserow Cloud on the baserow.io website, or
  * Self-hosted on your instance on-premise or in the cloud

No matter which version you choose, you can use Baserow for free or [upgrade to a paid plan](/user-docs/subscriptions-overview) in both the Baserow Cloud and Self-hosted.

For more details about pricing plans and features, visit the Baserow website to [purchase a paid plan](/pricing).

## Baserow open-source license

Almost all of the Baserow code is MIT-licensed and it is the most permissive license. As a permissive license, it puts only limited restrictions on reuse and has high license compatibility.

## Baserow Cloud

This is the easiest option, where you sign up on the [baserow.io](/) website and start using it right away. It’s perfect for getting started quickly.

Baserow Cloud has a free plan, but if you want more powerful features for your workspace, you’ll need to [upgrade to a paid plan](/user-docs/subscriptions-overview).

Learn more about [who is considered a “user” for billing purposes?](/user-docs/subscriptions-overview#who-is-considered-a-user-for-billing-purposes)

[Create an account](/signup)

| Free | Premium | Advanced  
---|---|---|---  
Yearly pricing | $0 | $10 per user / month | $20 per user / month  
Monthly pricing | $0 | $12 per user / month | $22 per user / month  
Row limit per workspace | 3,000 | 50,000 | 250,000  
Storage limit per workspace | 2GB | 20GB | 100GB  
Row change history | 14 days | 90 days | 180 days  
Features | Open source features | [Premium features](/user-docs/subscriptions-overview) | [Premium features](/user-docs/subscriptions-overview)  
Ideal for | Individuals and trials | Small companies | Mid-size companies  
User support | Community, knowledge base, tutorials | Community, knowledge base, tutorials | Direct support  
  
> The self-hosted version of Baserow does not have a rate limit. Baserow Cloud imposes a maximum of 10 concurrent requests. For optimal performance, consider that tables with fewer fields and rows generally process requests faster on Baserow Cloud.

## Self-hosted

You can host an application on a server you control and host the database on-premises or on a rented server in a data center. This gives you more control over your data and where it’s stored.

It is possible to run Baserow and register licenses on an air-gapped server, not connected to the internet. See our [installation documentation for options](/docs/index) for setting up a self-hosted Baserow server if you don’t already have one.

You’ll oversee the administration and maintenance of your server (usually on-premises), with complete control of all your data and services without depending on third-party providers.

To upgrade a Self-hosted version from a free to a paid plan, a subscription is purchased separately for a Baserow instance. You will need to [purchase a paid plan](/user-docs/subscriptions-overview) to allow your users access Baserow [premium features](/user-docs/subscriptions-overview).

[Self-host Baserow](/docs/index#installation)

| Open source | Premium | Enterprise  
---|---|---|---  
Yearly pricing | Free | $10 per user / month | On request  
Monthly pricing | Free | $12 per user / month | On request  
Row limit | Unlimited | Unlimited | Unlimited  
Storage limit | Unlimited | Unlimited | Unlimited  
Features | Open source features | [Premium features](/user-docs/subscriptions-overview) | [Premium](/user-docs/subscriptions-overview) and [Enterprise features](/user-docs/enterprise-license-overview)  
API requests limit | Unlimited | Unlimited | Unlimited  
Ideal for | Individuals and try out | Small companies | Larger teams  
User support | Community, knowledge base, tutorials | Community, knowledge base, tutorials | Direct support  
  
## Move data from Baserow Cloud to Self-hosted

To move your data from the Baserow Cloud to Self-hosted, you’ll need assistance from our team. Use the contact form to request a migration, and we’ll guide you through the process.

First, we’ll verify your data ownership, then create an export and provide instructions for importing it. Once you have the export, you can easily import your data into your self-hosted instance.

It’s important to note that this process requires some technical skills and familiarity with the command line.

[Contact support](/contact-sales)

## Troubleshooting

### Get help with Baserow

If you’re having any technical issues with setting up your Baserow account, or want to speak to someone about your account, you can reach out to Baserow Support.

If you’re wondering if the Baserow Cloud or Self-hosted is right for your business, [reach out for more information](/contact), we can help.

### Why do I receive a “Connection to the server failed” pop-up on [baserow.io](/)?

Baserow has an active web socket connection to receive real-time updates. The “Connection to the server failed” message on [baserow.io](/) is related to real-time collaboration. It indicates that there is a temporary issue with your connection to the Baserow server.

Temporary connection failures could be due to a variety of reasons, such as network instability, interruption in your internet connection, server downtime, or maintenance. This could happen if you lose your internet connection, put your device in sleep mode, or similar. Baserow will attempt to reconnect many times, but it will display a warning if that fails.

Here are a few steps you can take to troubleshoot this issue:

  1. Refresh the page: In many cases, the connection problem is usually temporary. You can restore the connection to the Baserow server by refreshing the page.

  2. Check your internet connection: Ensure that you have a stable and reliable internet connection. Try accessing other websites or online services to verify if the problem is specific to [baserow.io](/) or your internet connection in general.

  3. Verify server status: Check the [status page](/docs/index), [community](/user-docs/enterprise-license-overview), or official social media accounts for any known server issues or scheduled maintenance on [baserow.io](/).

  4. Contact Baserow support: If the issue persists or you suspect the issue is specific to your Baserow account, [contact the Baserow support team](/contact) for further assistance. The team can provide more specific guidance based on your account and help troubleshoot the connection problem.

### Need help self-hosting Baserow?

  * [Check out our installation guides](/docs/index).
  * [See the guide on configuring Baserow](/docs/installation%2Fconfiguration).
  * [Search the community for similar questions](https://community.baserow.io/search).

### Connection issues or server errors after install?

  * [Read our guide on debugging connection issues](/docs/tutorials%2Fdebugging-connection-issues).

## Related content

  * [Quick start](/user-docs/how-to-get-started-with-baserow)
  * [Introduction to Baserow](/user-docs/baserow-basics)
  * [Baserow glossary](/user-docs/learn-baserow-basic-concepts)
  * [Keyboard shortcuts](/user-docs/baserow-keyboard-shortcuts)

