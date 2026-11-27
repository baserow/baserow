<template>
  <div class="agent-channel-section">
    <AgentChannelCopyField
      :label="$t('agentChannels.embedCode')"
      :note="$t('agentChannels.embedCodeNote')"
      :text="embedCode"
      :copy-label="$t('agentChannels.copyCode')"
    />
  </div>
  <AgentPublicChatContent
    :channel="channel"
    :agent-name="agentName"
    :can-edit="canEdit"
    @update="$emit('update', $event)"
  />
  <div class="agent-channel-section">
    <FormSection :title="$t('agentChannels.appearance')">
      <FormGroup
        horizontal-narrow
        small-label
        class="margin-bottom-2"
        :label="$t('agentChannels.buttonText')"
      >
        <FormInput
          v-model="buttonText"
          class="agent-website-widget-form__button-text"
          :maxlength="BUTTON_TEXT_MAX_LENGTH"
          :disabled="!canEdit"
          @blur="saveButtonText"
        />
      </FormGroup>
      <FormGroup
        horizontal-narrow
        small-label
        required
        class="margin-bottom-2"
        :label="$t('agentChannels.buttonPosition')"
      >
        <SegmentControl
          class="agent-website-widget-form__position"
          size="small"
          :segments="positionSegments"
          :active-index="POSITIONS.indexOf(channel.button_position)"
          :disabled="!canEdit"
          @update:active-index="save('button_position', POSITIONS[$event])"
        />
      </FormGroup>
      <AgentChannelColorField
        :channel="channel"
        field="accent_color"
        :label="$t('agentChannels.accentColor')"
        :automatic-color="AUTOMATIC_ACCENT"
        :helper-text="$t('agentChannels.accentColorButtonNote')"
        :can-edit="canEdit"
        @update="$emit('update', $event)"
      />
    </FormSection>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useNuxtApp } from '#app'
import { useI18n } from 'vue-i18n'
import AgentChannelColorField from '@baserow_enterprise/components/agent/AgentChannelColorField'
import AgentChannelCopyField from '@baserow_enterprise/components/agent/AgentChannelCopyField'
import AgentPublicChatContent from '@baserow_enterprise/components/agent/AgentPublicChatContent'
import {
  AUTOMATIC_ACCENT,
  useChannelDraft,
} from '@baserow_enterprise/composables/useAgentChannels'

const BUTTON_TEXT_MAX_LENGTH = 60
const POSITIONS = ['bottom_left', 'bottom_right']

const props = defineProps({
  /** The website widget as its card shows it, edits included. */
  channel: { type: Object, required: true },
  /** The Agent's name, which the chat shows without a title. */
  agentName: { type: String, default: '' },
  /** Whether the user may change the website widget. */
  canEdit: Boolean,
})
const emit = defineEmits(['update'])
const { $registry } = useNuxtApp()
const { t } = useI18n()
const { draftOf, save } = useChannelDraft(props, emit)

const embedCode = computed(() =>
  $registry
    .get('agentChannelType', 'website_widget')
    .getEmbedCode(props.channel)
)
const positionSegments = computed(() => [
  { label: t('agentChannels.left') },
  { label: t('agentChannels.right') },
])
const buttonText = draftOf('button_text')

function saveButtonText() {
  buttonText.value = buttonText.value.trim()
  save('button_text', buttonText.value)
}
</script>
