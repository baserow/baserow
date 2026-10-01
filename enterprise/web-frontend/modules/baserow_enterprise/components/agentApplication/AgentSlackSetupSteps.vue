<template>
  <Expandable class="agent-configuration__setup">
    <template #header="{ toggle, expanded }">
      <a class="agent-configuration__expand-link" @click.prevent="toggle">
        <i class="iconoir-info-empty"></i>
        <span>{{ $t('agentSlackSetup.title') }}</span>
        <i
          class="agent-configuration__card-chevron iconoir-nav-arrow-down"
          :class="{ 'agent-configuration__card-chevron--expanded': expanded }"
        ></i>
      </a>
    </template>
    <ol class="agent-configuration__steps">
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
    </ol>
  </Expandable>
</template>

<script>
/**
 * Step-by-step guide for wiring a Slack app to a chat channel, shown inside
 * the channel card. The order matters: Slack only verifies the request URL
 * once the signing secret is saved, so the channel is created before the
 * event subscription is set up.
 */
export default {
  name: 'AgentSlackSetupSteps',
  props: {
    // Whether the channel exists already (its events URL is shown above).
    created: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
}
</script>
