# Baserow Documentation

Source: https://baserow.io/user-docs/field-level-permissions

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Field Level Permissions

![Implement field-level permissions in Baserow for enhanced data security](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/c328f77e-494b-4d92-8aa6-730d62b6a7eb/Field%20permissions.png)

## Overview

Field level permissions provide granular control over who can edit specific fields in your tables. This enterprise-grade feature is part of our Role-Based Access Control (RBAC) system and is available for Advanced and Enterprise users.

## Permission Levels

You can set the following permission levels for each field:

**Permission Level** | **Description**  
---|---  
Admins only | Field editing restricted to workspace administrators  
Builders and higher | Field editing available to builders and administrators  
Editors and higher | Default setting - allows editors, builders, and administrators to edit  
Nobody | Field becomes read-only for all users  
  
## Configuration Steps

  1. Open the table containing the field you want to configure
  2. Click on the field settings icon
  3. Navigate to the permissions section
  4. Select the desired permission level from the dropdown menu

## Form Integration

When using forms, you can further restrict field access by disabling the toggle to prevent this field from being set in rows created through forms.

