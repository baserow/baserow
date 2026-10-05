<template>
  <div>
    <SetupGuide :title="$t('agentSlackSetup.title')">
      <li>
        {{
          created
            ? $t('agentSlackSetup.manifestDownloadCreated')
            : $t('agentSlackSetup.manifestDownloadDraft')
        }}
      </li>
      <li>
        <i18n-t keypath="agentSlackSetup.manifestCreateApp" tag="span">
          <template #link>
            <a href="https://api.slack.com/apps" target="_blank" rel="noopener"
              >api.slack.com/apps</a
            >
          </template>
        </i18n-t>
      </li>
      <li>
        <i18n-t keypath="agentSlackSetup.install" tag="span">
          <template #prefix><code>xoxb-</code></template>
        </i18n-t>
      </li>
      <li>{{ $t('agentSlackSetup.signingSecret') }}</li>
      <li>{{ $t('agentSlackSetup.talk') }}</li>
    </SetupGuide>
    <SetupGuide :title="$t('agentSlackSetup.manualTitle')">
      <li>
        <i18n-t keypath="agentSlackSetup.createApp" tag="span">
          <template #link>
            <a href="https://api.slack.com/apps" target="_blank" rel="noopener"
              >api.slack.com/apps</a
            >
          </template>
        </i18n-t>
      </li>
      <li>
        <i18n-t keypath="agentSlackSetup.scopes" tag="span">
          <template #scopes>
            <code>chat:write</code>, <code>app_mentions:read</code>,
            <code>im:history</code>
          </template>
        </i18n-t>
      </li>
      <li>{{ $t('agentSlackSetup.messagesTab') }}</li>
      <li>
        <i18n-t keypath="agentSlackSetup.install" tag="span">
          <template #prefix><code>xoxb-</code></template>
        </i18n-t>
      </li>
      <li>{{ $t('agentSlackSetup.signingSecret') }}</li>
      <li>
        <i18n-t
          :keypath="
            created
              ? 'agentSlackSetup.eventsCreated'
              : 'agentSlackSetup.eventsDraft'
          "
          tag="span"
        >
          <template #events>
            <code>message.im</code>, <code>app_mention</code>
          </template>
        </i18n-t>
      </li>
      <li>{{ $t('agentSlackSetup.talk') }}</li>
    </SetupGuide>
  </div>
</template>

<script>
/**
 * Setup guides for wiring a Slack app to a chat channel, shown inside the
 * channel card: the short path creates the app from the channel's manifest,
 * the manual path clicks through the Slack app settings. Both end with the
 * bot token and signing secret pasted into the channel.
 */
export default {
  name: 'AgentSlackSetupSteps',
  props: {
    // Whether the channel exists already, which is when its manifest and
    // events URL are available.
    created: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
}
</script>
