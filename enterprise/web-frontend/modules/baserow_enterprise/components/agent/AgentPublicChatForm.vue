<template>
  <div class="agent-channel-section">
    <AgentChannelCopyField
      :label="$t('agentChannels.publicLink')"
      :note="$t('agentChannels.publicLinkNote')"
      :text="publicUrl"
      :copy-label="$t('agentChannels.copyURL')"
    />
  </div>
  <div class="agent-channel-section agent-public-chat-form__password">
    <SwitchInput
      class="agent-public-chat-form__password-switch"
      small
      role="switch"
      :tabindex="canEdit ? 0 : -1"
      :aria-checked="channel.has_password"
      :aria-disabled="!canEdit"
      :model-value="channel.has_password"
      :disabled="!canEdit"
      @update:model-value="togglePassword"
      @keydown.enter.prevent="togglePassword"
      @keydown.space.prevent="togglePassword"
    >
      <span>{{
        $t(
          channel.has_password
            ? 'agentChannels.passwordProtected'
            : 'agentChannels.restrictWithPassword'
        )
      }}</span>
    </SwitchInput>
    <a
      v-if="canEdit && channel.has_password"
      v-tooltip="$t('agentChannels.changePassword')"
      href="#"
      class="agent-public-chat-form__password-change"
      :aria-label="$t('agentChannels.changePassword')"
      @click.prevent="passwordModal.show()"
    >
      <i class="iconoir-edit-pencil" aria-hidden="true" />
    </a>
    <AgentPublicChatPasswordModal
      ref="passwordModal"
      :change="channel.has_password"
      :save="savePassword"
    />
    <AgentPublicChatDisablePasswordModal
      ref="disablePasswordModal"
      :disable="() => savePassword('')"
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
        required
        class="margin-bottom-2"
        :label="$t('agentChannels.background')"
      >
        <SegmentControl
          class="agent-public-chat-form__background"
          size="small"
          :segments="backgroundSegments"
          :active-index="BACKGROUNDS.indexOf(channel.background)"
          :disabled="!canEdit"
          @update:active-index="save('background', BACKGROUNDS[$event])"
        />
      </FormGroup>
      <AgentChannelColorField
        :channel="channel"
        field="background_color"
        :label="$t('agentChannels.backgroundColor')"
        :automatic-color="
          channel.background === 'gradient'
            ? AUTOMATIC_GRADIENT_TINT
            : AUTOMATIC_BACKGROUND
        "
        :can-edit="canEdit"
        @update="$emit('update', $event)"
      />
      <AgentChannelColorField
        :channel="channel"
        field="accent_color"
        :label="$t('agentChannels.accentColor')"
        :automatic-color="AUTOMATIC_ACCENT"
        :can-edit="canEdit"
        @update="$emit('update', $event)"
      />
    </FormSection>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useNuxtApp } from '#app'
import { useI18n } from 'vue-i18n'
import AgentChannelColorField from '@baserow_enterprise/components/agent/AgentChannelColorField'
import AgentChannelCopyField from '@baserow_enterprise/components/agent/AgentChannelCopyField'
import AgentPublicChatContent from '@baserow_enterprise/components/agent/AgentPublicChatContent'
import AgentPublicChatPasswordModal from '@baserow_enterprise/components/agent/AgentPublicChatPasswordModal'
import AgentPublicChatDisablePasswordModal from '@baserow_enterprise/components/agent/AgentPublicChatDisablePasswordModal'
import {
  AUTOMATIC_ACCENT,
  useChannelDraft,
} from '@baserow_enterprise/composables/useAgentChannels'

const BACKGROUNDS = ['gradient', 'plain']
// What the page shows behind its card for a blank background colour.
const AUTOMATIC_GRADIENT_TINT = '#fafafa'
const AUTOMATIC_BACKGROUND = '#ffffff'

const props = defineProps({
  /** The public chat as its card shows it, edits included. */
  channel: { type: Object, required: true },
  /** The Agent's name, which the public page shows without a title. */
  agentName: { type: String, default: '' },
  /** Whether the user may change the public chat. */
  canEdit: Boolean,
  /** Saves a new password, or removes it with '', and rejects when that fails. */
  savePassword: { type: Function, required: true },
})
const emit = defineEmits(['update'])
const { $config, $router } = useNuxtApp()
const { t } = useI18n()
const { save } = useChannelDraft(props, emit)
const passwordModal = ref(null)
const disablePasswordModal = ref(null)

const publicUrl = computed(
  () =>
    $config.public.baserowEmbeddedShareUrl +
    $router.resolve({
      name: 'agent-public-chat',
      params: { slug: props.channel.slug },
    }).href
)

const backgroundSegments = computed(() => [
  { label: t('agentChannels.backgroundGradient') },
  { label: t('agentChannels.backgroundPlain') },
])

/** The switch never changes the password itself; the modals do once confirmed. */
function togglePassword() {
  if (!props.canEdit) return
  const modal = props.channel.has_password
    ? disablePasswordModal
    : passwordModal
  modal.value.show()
}
</script>
