/**
 * The Slack app a "Create Slack app" link asks Slack to create. It carries
 * everything the "Send a Slack message" action needs, so the user has nothing
 * to configure in Slack before installing the app.
 *
 * https://docs.slack.dev/reference/app-manifest/
 */
export const SLACK_APP_MANIFEST = {
  display_information: { name: 'Baserow' },
  features: { bot_user: { display_name: 'Baserow' } },
  oauth_config: {
    scopes: {
      // `chat:write.public` lets the bot post to a public channel it was not
      // invited to. Slack only grants it together with `chat:write`.
      bot: ['chat:write', 'chat:write.public'],
    },
  },
}

/**
 * Returns the link that opens Slack's app creation flow with the manifest
 * already filled in. The user picks a workspace, reviews and creates the app.
 *
 * https://docs.slack.dev/app-manifests/configuring-apps-with-app-manifests/#sharing-manifests
 */
export const getSlackCreateAppUrl = (manifest = SLACK_APP_MANIFEST) => {
  const params = new URLSearchParams({
    new_app: '1',
    manifest_json: JSON.stringify(manifest),
  })
  return `https://api.slack.com/apps?${params}`
}
