export default (client) => {
  return {
    report(
      { resourceType, identifier, name, email, description, captchaToken },
      config = {}
    ) {
      return client.post(
        '/abuse-reports/',
        {
          resource_type: resourceType,
          identifier,
          name,
          email,
          description,
          captcha_token: captchaToken || '',
        },
        config
      )
    },
  }
}
