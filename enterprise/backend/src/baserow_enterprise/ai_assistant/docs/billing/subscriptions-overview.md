# Baserow Documentation

Source: https://baserow.io/user-docs/subscriptions-overview

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Subscriptions overview

Discover how to use and manage subscriptions for [Premium and Advanced plans](/user-docs/pricing-plans) in Baserow. This section covers how to upgrade from a free plan to a paid plan.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/4f350e43-8596-4600-a6d2-673f4a9e58fa/Screenshot%202023-01-27%20at%2010.24.31.png)

  * Active status → means that it hasn’t expired yet, even if it is canceled
  * Archived status → means subscription is no longer active
  * Not scheduled payment → means the subscription has been canceled and will not be renewed on expiry

> For Baserow Enterprise plans, pricing is calculated differently. Please get in [touch with a sales representative](/contact-sales) if you’re interested in learning more about Enterprise pricing.

## Baserow premium features

When upgraded to a [Premium, Advanced, or Enterprise plan](/user-docs/pricing-plans), the corresponding premium features are applied, including:

  * [JSON and XML export](/user-docs/export-tables)
  * [Row comments](/user-docs/enlarging-rows#commenting-on-rows)
  * [Row coloring](/user-docs/row-coloring)
  * [Public logo removal from forms](/user-docs/guide-to-creating-forms-in-baserow)
  * [Kanban view](/user-docs/guide-to-kanban-view)
  * [Calendar view](/user-docs/guide-to-calendar-view)
  * [Survey form mode](/user-docs/guide-to-creating-forms-in-baserow#form-survey-mode)
  * [Role-based permissions](/user-docs/permissions-overview) (Cloud Advanced and Self-Hosted Enterprise plans only)
  * Direct Priority Support (Cloud Advanced and Self-Hosted Enterprise plans only)
  * [Single Sign On](/user-docs/single-sign-on-sso-overview) (Self Hosted Enterprise plan only)
  * [Instance-wide admin access](/user-docs/enterprise-admin-panel) and workspace admin pages (Self Hosted Enterprise plan only)

For Baserow [Enterprise plan](/user-docs/enterprise-license-overview), all Premium features, plus role-based permissions, instance-wide admin panel, audit log, and priority support. For a full overview of our plans and pricing, please visit [https://baserow.io/pricing](/pricing).

## How paid subscriptions work

There are two main types of subscriptions:

  * Subscriptions for using our Cloud version at [baserow.io](http://baserow.io)
  * Subscriptions for using a self-hosted instance

Baserow offers both free and paid plans in the Cloud and Self Hosted versions. Our paid plans offer increased levels of usage and additional features.

### Subscription for Cloud plans

In the cloud version at [https://baserow.io](), subscription plans are on the workspace level. Subscription is purchased **separately for each Baserow workspace**. For example, if a user has two workspaces, they must get two subscriptions. It is possible to have multiple subscriptions for different workspaces as well as a combination of multiple free and paid workspaces.

> Only an admin of a workspace can access the workspace settings page to perform billing actions such as upgrading a workspace to another plan, updating billing information, and changing the subscription plan. Non-admin members of a workspace do not have access to its subscription information. For more details about workspace permissions, [please refer to this support article](/user-docs/working-with-collaborators#set-the-permission-level-for-collaborators).

When a workspace admin purchases a workspace subscription, the workspace and all collaborators are upgraded to that plan and you are charged for every user. You can’t have a mix of free and paid collaborators within a workspace.

#### Cloud Premium plan

When a workspace admin on a paid Cloud Premium plan invites a user to a workspace and the user accepts, they will be billed for that user. All the collaborators in the workspace will then have access to the [Baserow](/) premium features.

#### Cloud Advanced plan

You can invite someone to the workspace with the [Viewer, No Access, or No Role roles](/user-docs/permissions-overview) and you won’t have to pay for them unless you later change their roles. Learn more about [who is considered a user for billing purposes](/user-docs/subscriptions-overview#who-is-considered-a-user-for-billing-purposes).

For more details on how to purchase a paid subscription for the cloud version, [please refer to this support article](/user-docs/buying-a-subscription).

### Subscription for Self-hosted plans

In the self-hosted version, the plans are on a **server-wide level**. A **subscription is purchased separately for a Baserow instance** , identified by an instance ID. You can mix free and paid users in one Baserow instance and it doesn’t matter in which workspaces the users will work in.

> Only an Instance Admin can access the Admin panel to retrieve the instance ID required to perform billing actions. Users without staff access do not have access to the entire instance.

#### Self-hosted Premium plan

Billing is based on the number of seats. Users on the Self-hosted Premium plan can buy subscriptions per seat and can manually assign seats per user, irrespective of the workspace they are in.

You can choose the number of seats you want to purchase at the beginning and adjust the number of seats at any time. The number of seats is the number of users that you can give access to the premium version in your self-hosted environment.

This makes it possible to have multiple premium licenses in one instance if desired. If you have 100 free users in total, you can buy a license for 10 seats and assign 10 users to it, meaning 10 users will have premium and 90 are free. This can be combined.

#### Self-hosted Enterprise plan

The Enterprise Self-hosted license upgrades all users at once without you having to do anything after registering it. If a user [buys a license and upgrades their instance](/user-docs/activate-enterprise-license), it’s for all users regardless, even if they have multiple workspaces.

For more details on how to purchase a paid subscription for the Self-hosted version, [please refer to this support article](/user-docs/buying-a-subscription#buy-a-subscription-for-the-self-hosted-version).

## How to check your Cloud plan

You can view a workspace’s subscription plan next to its name on the [dashboard](/dashboard) in the Cloud version.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/a205e3df-8a8b-4de2-ae81-5da9c4685f63/Screenshot%202022-12-20%20at%2018.56.21.png)

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/263248ef-20ca-41a8-9990-58cfa726f666/Screenshot%202022-12-20%20at%2019.01.56.png)

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/6a9d7381-dff8-4401-b56e-4ddd781ea919/Screenshot%202022-12-20%20at%2018.58.26.png)

## Who is considered a “user” for billing purposes?

Baserow has both free and paid plans available. Pricing is per user/month.

Users are either billable or non-billable. Billable users count toward your subscription plan, while non-billable users do not. Paid plans are charged per user or per seat.

Pricing Plan | User  
---|---  
Free plan | Users on the free plan are not billed. Baserow free plan is ideal for individuals or very small teams.  
Cloud Premium plan | Every collaborator in a workspace is classified as billable on the Cloud Premium paid plan. Billing is automatically based on all the users in a workspace. The entire workspace is upgraded and you are charged for every collaborator in the workspace.  
Cloud Advanced plan | Any workspace collaborator with the roles of Editor, Builder, or Admin is billable on the Cloud Advanced paid plan. Workspace collaborators who have read-only roles, including the Commenter, Viewer, No Access, and No Role, are classified as non-billable and completely free. Billing is automatically based on the number of users with paid roles in a workspace.  
Self-Hosted Premium plan | You are billed for a fixed number of seats. Users can be allocated these seats on demand. Any seat assigned to users in the entire instance is classified as billable per seat.  
Self-Hosted Enterprise plan | Users classed as billable will be decided with Baserow’s sales team. The Self-Hosted Baserow Enterprise plan is designed for large businesses that want to get the most out of Baserow. Please [contact a sales representative ](/contact-sales) to understand how the Enterprise plan will work for your team.  
  
The price is prorated every time the [number of users changes](/user-docs/change-a-paid-subscription), so you will get charged only for the time during which a user can use premium features. If you remove a user, the remainder of the money charged will be used for the next payments.

In the **Cloud Premium and Advanced plans** , assigning a billable role to a free user or inviting users with a billable role to your workspace partway through a billing period will cause a pro-rated charge to be taken from your credit card on that or the following day.

Alternatively, removing users with paid roles from the workspace will result in a pro-rated credit being applied to your account which will be used to reduce the price of your next billing period.

> Users are considered to be a part of a workspace once they accept an invitation to join. Sending invitations by itself doesn’t lead to additional charges.

In the **Self-Hosted plans** , the price will be pro-rated when the [number of seats change](/user-docs/change-a-paid-subscription).

For details and pricing for each plan, please visit [/pricing](/pricing).

