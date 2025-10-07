# Setting up SAML SSO for development

* Create a new SAML authentication provider by going to 
  http://localhost:3000/admin/auth-providers and clicking on "Add provider" and then on
  "SSO SAML provider".
* Set SAML Domain to `example.com`.
* Go to https://mocksaml.com/ and click on "Download Metadata". Put the contents of the
  file in the Metadata input.
* Open the SAML Response Attributes and set the following.
  * Email: `email`
  * First name: `firstName`
  * Last name: `lastName`
* Click on save, logout and try to log in using the newly created SAML provider. 
* Observe that you're redirected to the https://mocksaml.com login page where you can
  use any @example.com address to log in with.
