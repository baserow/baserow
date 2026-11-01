# Secure File Serving

This document outlines the steps to enable secure file serving in Baserow, a feature
that allows the backend to serve files directly without needing another web server. This
capability introduces several benefits, including the ability to set expiration times
for file links and enforce access controls based on user authentication and workspace
membership. However, it's important to weigh these benefits against potential
performance costs and other considerations.

Note that this is an enterprise feature.

## Configuration

To enable secure file serving, you must configure the following environment variables
in your Baserow instance:

1. **BASEROW_SERVE_FILES_THROUGH_BACKEND**: Set this variable to `true` to activate
   backend file serving. This feature is disabled by default. Note that enabling this
   setting does not automatically secure your storage server against unauthorized 
   access. You should take additional security measures if your storage server serves
   files publicly.

2. **BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION**: This variable controls access
   permissions for downloading files. The default setting, `DISABLED`, allows anyone to 
   download files. To restrict downloads to signed-in users, set this to `SIGNED_IN`.
   For tighter control, where only users with workspace access can download files, use
   `WORKSPACE_ACCESS`.

3. **BASEROW_SERVE_FILES_THROUGH_BACKEND_EXPIRE_SECONDS**: Use this variable to set an
   expiration time for file links, specified in seconds. Unset, or set this to a
   non-positive integer, makes file links permanent. Setting a positive integer will
   make the link expire after the specified duration, enhancing security by preventing
   outdated link access.

## Benefits

- **Enhanced Security**: Direct backend serving of files allows for more granular
  control over who can access files and when.
- **Expiration Times**: Ability to set expiration times for file links, reducing the
  risk of unauthorized access to files over time.
- **Access Control**: Ensures that files can only be downloaded by users who are either
  logged in or have specific workspace access, based on your configuration.

## Considerations

- **Performance Cost**: Serving files through the backend can introduce a performance
  overhead. It may necessitate deploying additional backend (asgi or wsgi) workers to
  maintain fast response times.
- **Enterprise License Required**: This feature requires a valid enterprise license to
  activate.
- **Domain Restrictions for Cookie-Based Authentication**: If using cookie-based user
  checks, the Baserow instance must be on the same domain or subdomains as the frontend.
  Cross-domain setups will not support this authentication method.
- **User Re-authentication**: Users must sign in again after this feature is enabled to
  ensure proper access control.
- **Publicly Shared Files**: Depending on the configured permission level, files that 
  are publicly shared through applications, views, or APIs may become inaccessible.
- **Files Opened Directly**: Images, PDFs and plain text files display in the browser.
  Everything else downloads, including HTML, SVG, CSV, JSON, Markdown, audio, video and
  files without an extension. Images, audio and video shown inside Baserow are not
  affected. Every file is also served with a `sandbox` Content-Security-Policy, the same
  one used for `/media/`, so a displayed file can't run script on the Baserow origin.

## Steps to Enable

1. Ensure you have a valid enterprise license for Baserow.
2. Configure the environment variables as described in the Configuration section above.
3. If your files were previously served directly from a storage service like S3, adjust
   your storage service settings to ensure files are no longer publicly accessible.
   Baserow will now handle file serving.
4. Consider the performance implications and plan for additional backend workers if
   necessary.
5. Inform users that they may need to sign in again to access files after these changes.

By following these steps and considerations, you can securely serve files through 
Baserow, enhancing the security and control over file access within your organization.
