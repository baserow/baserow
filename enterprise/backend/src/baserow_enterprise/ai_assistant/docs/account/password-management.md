# Baserow Documentation

Source: https://baserow.io/user-docs/password-management

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Password management

This article describes how to change your account password and the Baserow requirements for a password.

## Setting your account password

When you create a new Baserow account, you will be required to create a password with a minimum of 8 characters is required. Once you’ve added a password, you’ll be able to access your Baserow account using your email address and password.

## Change an existing password

Open your Baserow account page to find your password information. To change your password,

  1. Click the profile icon in the top left of your screen.
  2. In the popup menu, select the **Settings** option.
  3. In the settings, navigate to the **Password** tab.
  4. You’ll need to enter your Old password, New password and Repeat new password in the text fields.
  5. To confirm a change to your password, click **Change password**. !Change password][1](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-06-15_at_13.34.08.png)

## How to reset your password

To recover your password, fill out the [forgot password form](/forgot-password) with your email address. If an account is discovered, we will email you a link to reset your password.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/Screenshot_2022-07-01_at_15.23.18.png)

### Local Docker instances without email

If you’re running Baserow locally with Docker and don’t have email configured, the reset link will appear in your container logs instead:

  1. Submit the forgot password form with your email address
  2. Check your Docker container logs: `docker logs [container_name]`
  3. Search for “reset-password” in the logs to find the reset URL
  4. Copy the complete URL and paste it into your browser
  5. Create your new password and login with it

**Quick search commands:**

  * **Linux/Mac:** `docker logs [container_name] | grep "reset-password"`
  * **Windows CMD:** `docker logs [container_name] | findstr "reset-password"`
  * **Windows PowerShell:** `docker logs [container_name] | Select-String "reset-password"`

