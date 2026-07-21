export default (client) => {
  return {
    report(
      { resourceType, identifier, name, email, description },
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
        },
        config
      )
    },
  }
}
