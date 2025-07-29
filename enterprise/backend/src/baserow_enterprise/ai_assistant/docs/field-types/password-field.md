# Baserow Documentation

Source: https://baserow.io/user-docs/password-field

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Password field

The password field type in Baserow enhances data security by allowing you to set passwords for each row. It offers secure storage for passwords within your database and allows you to create rows with password data.

In this section, we will explore the password field in Baserow, ensuring robust security measures for your data.

![Password field type in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9597b3d5-a8c6-48c7-bfbe-16aa0513487d/Untitled.png)

## Overview

With the password field, you can implement access controls and authentication measures in Baserow [Application Builder](/user-docs/application-builder-overview), maintaining the privacy and security of your data.

  1. **Write-only functionality** : The password field type ensures that passwords are stored securely as hashes and are never revealed or displayed, enhancing security and protecting user privacy.
  2. **User authentication** : The password field type is a significant addition for [applications](/user-docs/application-builder-overview) requiring user authentication. With the password field, you can implement robust user authentication mechanisms within the application builder. Users can securely log in using their passwords without compromising sensitive information.
  3. **Hashed storage** : Passwords are stored as hashes, which adds an additional layer of security. This helps mitigate the risk of unauthorized access and data breaches.
  4. **Enhanced security** : The password field type strengthens the overall security posture of applications by adhering to best practices for password management and storage. It reduces the likelihood of security vulnerabilities associated with plaintext password storage.

## Add a password field

To add a password field, follow these steps:

  1. Click the plus sign `+` to the right of your existing fields.
  2. Select the **Password** type and name the field. You can add a unique field name in the customization menu.
  3. Click **Create**.

This will create a new field in your database designed to store passwords securely.

## Related content

  * [Field overview](/user-docs/baserow-field-overview).
  * [Create a field](/user-docs/adding-a-field).
  * [Field configuration options](/user-docs/field-customization).
  * [Filter by a field in Baserow](/user-docs/filters-in-baserow).
  * [Group by a field](/user-docs/group-rows-in-baserow).

