# Baserow Documentation

Source: https://baserow.io/user-docs/pricing-plans

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Pricing plans

An overview of the various Baserow plans can be found below. We provide cloud and self-hosted plans.

We recommend visiting the Baserow [pricing page](/pricing) for the most up-to-date information.

While all self-hosted instances on-premise or in the cloud allow you to create an unlimited number of databases, rows, and storage, the cloud offering on the [baserow.io](http://baserow.io/) website has limits on the number of rows and storage.

> The self-hosted version of Baserow does not have a rate limit. The cloud version imposes a maximum of 10 concurrent requests. For optimal performance, consider that tables with fewer fields and rows generally process requests faster on the cloud version.

## Free plan

When you first create a workspace, the free plan will be the default workspace plan.

> The free plan is available in both the cloud and the Self-hosted versions.

There are, however, some limitations to be aware of. A free cloud plan restricts each workspace to a maximum of 3000 rows and 2GB of storage. This total includes data from multiple databases. For instance, a workspace with a single database with 3500 rows and a workspace with two databases with 2000 rows each, would both exceed the free plan’s limits. If a workspace exceeds its row limit for 7 days, you won’t be able to create new rows. You’ll receive an error message explaining that you must either upgrade your plan or reduce your row count to continue adding data.

Here’s a breakdown of the core usage differences between the free cloud and self-hosted plans:

| Cloud | Self-host  
---|---|---  
Databases | Unlimited | Unlimited  
Rows | 3000 per workspace | Unlimited  
Storage | 2GB per workspace | Unlimited  
  
The free plan has other core limitations in both the Cloud and Self-hosted versions.

**JSON and XML export**

The free plan does not allow users to download data from tables by exporting them as JSON or XML files.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/879b4b55-a14b-4d50-b92d-ec0c5169b5eb/Screenshot_2022-12-20_at_23.34.06.png)

**Row comments**

The free plan does not include [row commenting](/user-docs/enlarging-rows), which allows for communication and collaboration with workspace members.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d64cb2ba-20e4-4045-be45-b6f2324ae680/Screenshot_2022-12-20_at_23.35.53.png)

**Row coloring**

[Row coloring](/user-docs/row-coloring), which allows you to automatically color rows by using custom filtering conditions or single select fields, is not available on the free plan.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/cd53da67-d598-4cac-921c-82250af028e0/Untitled.png)

**Public logo removal**

The Baserow branding cannot be removed from the free plan.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/321b3e2e-1d7c-4bb1-92c0-c61c2691d0e2/Screenshot_2022-12-20_at_23.31.35.png)

**Role-based permissions**

The ability to [assign roles](/user-docs/permissions-overview) to various workspace collaborators to manage who has access to data and can perform important actions is not available in the free plan.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/aaf8daf7-a581-4a96-84df-2f596bb2415e/Untitled%201.png)

**Kanban view**

On the free plan, displaying data in visual cards is not available.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/93eecac3-b1f9-4439-85b5-8b99011a1495/Untitled%202.png)

**Survey form mode**

Forms cannot be customized with survey form mode on the free plan.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d8e5e641-b23e-4acf-906d-a3de3523fd1c/Screenshot_2022-12-20_at_23.32.12.png)

If one of your workspaces exceeds these limits, you will be prompted to upgrade the workspace to a premium or advanced plan, which includes many additional features as well as increased row and storage limits.

**Calendar view**

The calendar view is not accessible on the free plan. You’ll need to upgrade to a paid plan to use the calendar view.

## Premium plan

The Baserow Premium plan costs $10 per user/month billed yearly, and $12 per user/month billed monthly. Please see this article for a detailed explanation of [who is considered a user for billing purposes](/user-docs/subscriptions-overview#who-is-considered-a-user-for-billing-purposes).

> The premium plan is available in both the Cloud and the Self-hosted versions. To upgrade your plan, please [refer to this support article](/user-docs/buying-a-subscription).

Compared to the free plan, our Premium plan offers premium features including increased record limits, JSON and XML export, [row comments](/user-docs/enlarging-rows), [row coloring](/user-docs/row-coloring), public logo removal, Kanban view, Calendar view, and Survey form mode.

There are, however, some limitations to be aware of. A premium Cloud plan restricts each workspace to a maximum of 50000 rows and 20GB of storage. This total includes data from multiple databases. For instance, a workspace with a single database with 55000 rows and a workspace with two databases with 26000 rows each would both exceed the premium plan’s limits in the Cloud version. If a workspace exceeds its row limit for 7 days, you won’t be able to create new rows. You’ll receive an error message explaining that you must either upgrade your plan or reduce your row count to continue adding data.

Here’s a breakdown of the core usage differences between the premium Cloud and Self-hosted plans:

| Cloud | Self-hosted  
---|---|---  
Databases | Unlimited | Unlimited  
Rows | 50000 per workspace | Unlimited  
Storage | 20GB per workspace | Unlimited  
  
The premium plan has other core limitations in both the Cloud and Self-hosted versions:

**Role-based permissions**

The [role-based permission feature](/user-docs/permissions-overview), which lets you control who has access to resources and data and what they can do with it, is not available on the Premium plan. This feature is only available on Advanced and Enterprise plans.

**Admin access**

Instance-wide admin panel, Single Sign-On (SSO), and Payment by Invoice are features only available for Baserow Enterprise plans.

Direct Priority Support is only available for Baserow Cloud Advanced and Self-hosted Enterprise plans.

## Advanced plan

The Baserow Advanced plan costs $22 per user/month billed monthly, and $20 per user/month billed yearly. There is a fixed price per user for non-viewers, regardless of their role as Admin, Builder, or Editor. It is not possible to charge different prices for different roles. Please see this support article for a detailed explanation of [who is considered a user for billing purposes](/user-docs/subscriptions-overview#who-is-considered-a-user-for-billing-purposes).

> The Advanced plan available in the Cloud and Self-Hosted versions. Can be mixed with Free users in a self-hosted isntance as license is instance based. Includes App Builder license for Builders.
> 
> For self-hosters, you get everything from the cloud version + SSO + Audit log + instance wide admin
> 
> To upgrade your cloud plan, please [refer to this support article](/user-docs/buying-a-subscription).

Our Advanced plan also provides access to premium features including increased record limits, JSON and XML export, [row comments](/user-docs/enlarging-rows), [row coloring](/user-docs/row-coloring), public logo removal, Kanban view, Survey form mode, Direct Priority Support, and [Role based permissions](/user-docs/permissions-overview).

There are, however, some limitations to be aware of. An Advanced cloud plan restricts each workspace to a maximum of 250000 rows and 100GB of storage. This total includes data from multiple databases. For instance, a workspace with a single database with 260000 rows and a workspace with two databases with 150000 rows each would both exceed the premium plan’s limits. If a workspace exceeds its row limit for 7 days, you won’t be able to create new rows. You’ll receive an error message explaining that you must either upgrade your plan or reduce your row count to continue adding data.

Instance-wide admin panel, Single Sign-On (SSO), and Payment by Invoice are features only available for Baserow self-hosted Enterprise plans.

## Enterprise plan

For Baserow Enterprise plans, pricing is calculated differently. The Enterprise plan is available only in the Self-hosted version.

Please get in [touch with a sales representative](/contact-sales) if you’re interested in learning more about Enterprise pricing.

