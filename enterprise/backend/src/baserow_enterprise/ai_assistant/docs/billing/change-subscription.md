# Baserow Documentation

Source: https://baserow.io/user-docs/change-a-paid-subscription

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Change a paid subscription

When you subscribe to a paid plan in teh cloud version, all the collaborators in the workspace will be upgraded to that plan. Inviting more collaborators to the workspace will increase the price of your subscription as all collaborators in the workspace must be premium. Likewise, the price will be reduced once the user is not a part of the workspace anymore.

## Create a new subscription for Cloud version

To create a new subscription (upgrade a workspace), navigate to the **Subscriptions** section and select your workspace upgrade option.

When you create a new subscription for the Cloud version:

  * All users in the workspace are automatically put on the plan
  * Once a new user accepts an invitation, the buyer is automatically charged within 24 hours
  * The difference is calculated pro rata for the remaining days until your next payment
  * Viewer and commenters are free, but this must be the highest role they have in the workspace
  * If they’re an editor in even one single table, they would need to pay for a full seat

## Create a new subscription for Self-hosted version

For self-hosted subscriptions, you can create a new subscription and manually set the number of seats. The number of seats determines how many users can access the premium features in your self-hosted environment.

When creating a self-hosted subscription:

  * You need to fill out the number of seats manually
  * You can increase or decrease the number of seats after getting the license
  * The difference is calculated pro rata for the remaining days until your next payment
  * The instance ID can be changed for a subscription

## Change subscription in the Cloud version

To change your subscription, navigate to the **Subscriptions** > **More details**.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fbc8d348-60f0-43c1-83ee-28ab2473d850/Screenshot_2022-08-10_at_09.32.00.png)

Within the subscription details, you can view the row and storage usage, as well as change payment method, change subscription, download receipt, and view the next payment date.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/a00ef1e6-61fd-4d3f-8bd2-da85e47bdf6d/Screenshot_2022-08-10_at_09.33.35.png)

To change a subscription, click on the **Change subscription** link and select a new plan and/or period. Next, click the **Confirm change** button.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/c5a80933-f82b-4272-96aa-ad1a99365e46/Screenshot_2022-08-10_at_09.39.12.png)

### Switching between Premium and Advanced plans

It’s possible to switch from premium to advanced and vice versa. No money will be paid back, but the remainder will be calculated pro rata for your account.

## Change seats in the Self-hosted version

Self-hosters can choose the number of seats and adjust them as needed.

> To upgrade or downgrade the self-hosted plan’s seats as an existing self-hosting subscriber, visit the [Baserow.io](http://Baserow.io) Cloud version to make a change to the subscription.

To adjust the number of seats for self-hosters, click on the **More details** button.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/dc050572-9285-4587-9021-244e16062397/Screenshot_2022-08-10_at_09.55.02.png)

Within the details page, click on the **Change subscription** link and update the number of seats, plan, instance ID and/or payment period.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/83cb7cb4-8f3b-411d-b20a-a38d43fa01ac/Screenshot_2022-08-10_at_10.09.57.png)

As you add new seats, the cost of the subscription will change to reflect the new pricing.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/5e36e733-1d7d-4634-8881-6115c115f9b2/Screenshot_2022-08-10_at_10.14.28.png)

Next, click the **Confirm change** button. If you add a user you will get charged the difference right away. If you remove a user, the remainder of the money charged will be used for the next payments.

## Self-hosted license management

### Premium self-hosted licenses

Once a premium self-hosted license is registered:

  * You need to choose which users are using the seats
  * It’s possible to combine multiple premium licenses if needed
  * You have control over which specific users get premium access

### Advanced self-hosted licenses

Once an advanced self-hosted license is registered:

  * All users on the instance will be on that license
  * It’s not possible to combine multiple licenses because all users of the instance must be on it
  * Currently, there are no strict limitations, so you can buy one seat and use it with 100 users
  * **Important** : This is going to change soon - we will automatically make users outside the license read-only

## Change an instance ID

Your instance ID can be found in the admin licenses section and can be changed.

It is also possible to change the `instance id` for an ongoing subscription in case you want to use the license for a different instance later on.

## Change the payment method

You can update your payment method within your Cloud or Self-hosted subscription details.

To update your payment method, follow these steps:

  1. Visit [Baserow subscriptions](/subscriptions) page. Even if you are self-hosting, you must access the SaaS version on [Baserow.io](http://Baserow.io) to manage your subscription.
  2. Find your subscription and click **More details**.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/f4e39f92-1a63-4d3d-a54f-411b8221a249/Screenshot_2022-08-10_at_09.57.26.png)

  3. In the top-right corner, locate the _Payment information_ section.
  4. Within the details page, click on **Change payment method** to proceed to provide new payment card details.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9373852f-7356-42d9-bbe4-b39ac0747978/Screenshot_2022-08-10_at_09.59.09.png)

You will be redirected to a new window to update payment card information.

## Cancel a subscription

A paid subscription stays active for the pre-paid period and ends on the day the next payment would occur.

**Important** : If a subscription is cancelled, no money is paid back because it remains active until the end of the period.

To cancel your subscription,

  1. Navigate to the **Subscriptions** tab > **More details**.
  2. Click on the **Change subscription** link
  3. Click the **Cancel subscription** link.

When a subscription is canceled, it will remain active until the end of the billing period.

## Pro rata billing

For all subscription changes, billing is calculated pro rata:

  * When adding users or upgrading plans, you’re charged the difference for the remaining days until your next payment
  * When downgrading or removing users, the remainder is credited toward future payments
  * Automatic billing occurs within 24 hours when new users accept invitations in Cloud workspaces

