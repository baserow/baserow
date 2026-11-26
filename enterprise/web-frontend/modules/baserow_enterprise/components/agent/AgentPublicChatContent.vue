<template>
  <div class="agent-channel-section">
    <FormGroup
      class="agent-channel-section__field"
      :label="$t('agentChannels.title')"
      small-label
    >
      <FormInput
        v-model="title"
        class="agent-public-chat-content__title-input"
        :placeholder="agentName"
        :maxlength="TITLE_MAX_LENGTH"
        :disabled="!canEdit"
        @blur="save('title', title)"
      />
    </FormGroup>
    <FormGroup
      class="agent-channel-section__field"
      :label="$t('agentChannels.welcomeText')"
      small-label
      :error="welcomeTextTooLong"
    >
      <RichTextEditor
        ref="welcomeEditor"
        class="form-input field-rich-text agent-public-chat-content__welcome-text"
        :model-value="channel.welcome_text"
        :editable="canEdit"
        :enable-rich-text-formatting="true"
        :allow-identity-suggestions="false"
        @update:model-value="welcomeTextChanged = true"
        @blur="saveWelcomeText"
      />
      <template #error>{{
        $t('agentChannels.welcomeTextTooLong', {
          max: WELCOME_TEXT_MAX_LENGTH,
        })
      }}</template>
    </FormGroup>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor'
import { useChannelDraft } from '@baserow_enterprise/composables/useAgentChannels'

const TITLE_MAX_LENGTH = 160
const WELCOME_TEXT_MAX_LENGTH = 2000

const props = defineProps({
  /** A public chat, or a channel type built on one, as its card shows it. */
  channel: { type: Object, required: true },
  /** The Agent's name, which the chat shows without a title. */
  agentName: { type: String, default: '' },
  /** Whether the user may change the channel. */
  canEdit: Boolean,
})
const emit = defineEmits(['update'])
const { draftOf, save } = useChannelDraft(props, emit)

const title = draftOf('title')
const welcomeEditor = ref(null)
const welcomeTextTooLong = ref(false)
let welcomeTextChanged = false

function saveWelcomeText() {
  if (!welcomeTextChanged) return
  const markdown = welcomeEditor.value.serializeToMarkdown()
  // Counted in code points, as the server counts them.
  welcomeTextTooLong.value = [...markdown].length > WELCOME_TEXT_MAX_LENGTH
  if (welcomeTextTooLong.value) return
  welcomeTextChanged = false
  save('welcome_text', markdown)
}
</script>
