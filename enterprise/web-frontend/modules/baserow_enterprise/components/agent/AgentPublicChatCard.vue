<template>
  <article class="agent-public-chat-card" :aria-busy="saving">
    <header class="agent-public-chat-card__header">
      <button
        type="button"
        class="agent-public-chat-card__toggle"
        :aria-expanded="expanded"
        :aria-label="$t('agentChannels.settings', { name: shownName })"
        @click="$emit('toggle')"
      >
        <Icon
          :icon="
            expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'
          "
          aria-hidden="true"
        />
        <Icon
          icon="iconoir-multi-bubble"
          class="agent-public-chat-card__icon"
          aria-hidden="true"
        />
        <span class="agent-public-chat-card__name">{{ shownName }}</span>
      </button>
      <span class="agent-public-chat-card__saving-slot">
        <span
          v-if="saving"
          class="agent-public-chat-card__saving"
          role="status"
          :aria-label="$t('agent.saving')"
        />
      </span>
      <SwitchInput
        class="agent-public-chat-card__switch"
        small
        role="switch"
        :tabindex="canSwitch ? 0 : -1"
        :aria-label="$t('agentChannels.publicChatEnabled')"
        :aria-checked="channel.enabled"
        :aria-disabled="!canSwitch"
        :model-value="channel.enabled"
        :disabled="!canSwitch"
        @update:model-value="$emit('update', { enabled: $event })"
        @keydown.enter.prevent="toggleEnabled"
        @keydown.space.prevent="toggleEnabled"
      />
    </header>
    <div v-show="expanded" class="agent-public-chat-card__body">
      <div class="agent-public-chat-card__section">
        <FormGroup
          class="agent-public-chat-card__field"
          :label="$t('agentChannels.publicLink')"
          small-label
          required
        >
          <p class="agent-public-chat-card__link-description">
            {{ $t('agentChannels.publicLinkNote') }}
          </p>
          <div class="agent-public-chat-card__link">
            <div class="agent-public-chat-card__link-box">{{ publicUrl }}</div>
            <a
              v-tooltip="$t('agentChannels.copyURL')"
              href="#"
              class="agent-public-chat-card__copy"
              :aria-label="$t('agentChannels.copyURL')"
              @click.prevent="copyLink"
            >
              <i class="iconoir-copy" aria-hidden="true" />
              <Copied ref="copied" />
            </a>
          </div>
        </FormGroup>
      </div>
      <div
        class="agent-public-chat-card__section agent-public-chat-card__password"
      >
        <SwitchInput
          class="agent-public-chat-card__password-switch"
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
          class="agent-public-chat-card__password-change"
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
      <div class="agent-public-chat-card__section">
        <FormGroup
          class="agent-public-chat-card__field"
          :label="$t('agentChannels.title')"
          small-label
        >
          <FormInput
            v-model="title"
            class="agent-public-chat-card__title-input"
            :placeholder="agentName"
            :maxlength="TITLE_MAX_LENGTH"
            :disabled="!canEdit"
            @blur="saveDraft('title', title)"
          />
        </FormGroup>
        <FormGroup
          class="agent-public-chat-card__field"
          :label="$t('agentChannels.welcomeText')"
          small-label
          :error="welcomeTextTooLong"
        >
          <RichTextEditor
            ref="welcomeEditor"
            class="form-input field-rich-text agent-public-chat-card__welcome-text"
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
    </div>
    <footer
      v-if="editable"
      v-show="expanded"
      class="agent-public-chat-card__footer"
    >
      <ButtonText
        type="secondary"
        size="small"
        button-type="button"
        icon="iconoir-bin"
        class="agent-public-chat-card__delete"
        @click="$emit('delete')"
      >
        {{ $t('agentChannels.deletePublicChat') }}
      </ButtonText>
    </footer>
  </article>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useNuxtApp } from '#app'
import { useI18n } from 'vue-i18n'
import Icon from '@baserow/modules/core/components/Icon'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor'
import { copyToClipboard } from '@baserow/modules/core/utils/clipboard'
import AgentPublicChatPasswordModal from '@baserow_enterprise/components/agent/AgentPublicChatPasswordModal'
import AgentPublicChatDisablePasswordModal from '@baserow_enterprise/components/agent/AgentPublicChatDisablePasswordModal'

const TITLE_MAX_LENGTH = 160
const WELCOME_TEXT_MAX_LENGTH = 2000

const props = defineProps({
  /** The public chat as the card shows it, edits included. */
  channel: { type: Object, required: true },
  /** The Agent's name, which the public page shows without a title. */
  agentName: { type: String, default: '' },
  /** Whether the user may change the public chat. */
  editable: Boolean,
  /** Without the licence, only switching the chat off and deleting it remain. */
  licensed: Boolean,
  /** Saves a new password, or removes it with '', and rejects when that fails. */
  savePassword: { type: Function, required: true },
  /** Whether the card shows its settings below its header. */
  expanded: Boolean,
  /** Whether a save of the public chat is in flight. */
  saving: Boolean,
})
const emit = defineEmits(['toggle', 'update', 'delete'])
const { $config, $router } = useNuxtApp()
const { t } = useI18n()
const copied = ref(null)
const passwordModal = ref(null)
const disablePasswordModal = ref(null)

const canEdit = computed(() => props.editable && props.licensed)
const canSwitch = computed(
  () => canEdit.value || (props.editable && props.channel.enabled)
)
const shownName = computed(
  () => props.channel.title || t('agentChannels.publicChat')
)
const publicUrl = computed(
  () =>
    $config.public.baserowEmbeddedShareUrl +
    $router.resolve({
      name: 'agent-public-chat',
      params: { slug: props.channel.slug },
    }).href
)

/**
 * @param {string} field The channel field the draft edits.
 * @returns {import('vue').Ref<string>} A draft that follows the saved value.
 */
function draftOf(field) {
  const draft = ref(props.channel[field])
  watch(
    () => props.channel[field],
    (value) => {
      draft.value = value
    }
  )
  return draft
}

const title = draftOf('title')
const welcomeEditor = ref(null)
const welcomeTextTooLong = ref(false)
let welcomeTextChanged = false

function saveDraft(field, value) {
  if (canEdit.value && value !== props.channel[field]) {
    emit('update', { [field]: value })
  }
}

function saveWelcomeText() {
  if (!welcomeTextChanged) return
  const markdown = welcomeEditor.value.serializeToMarkdown()
  // Counted in code points, as the server counts them.
  welcomeTextTooLong.value = [...markdown].length > WELCOME_TEXT_MAX_LENGTH
  if (welcomeTextTooLong.value) return
  welcomeTextChanged = false
  saveDraft('welcome_text', markdown)
}

function copyLink() {
  copyToClipboard(publicUrl.value)
  copied.value.show()
}

function toggleEnabled() {
  if (canSwitch.value) emit('update', { enabled: !props.channel.enabled })
}

/** The switch never changes the password itself; the modals do once confirmed. */
function togglePassword() {
  if (!canEdit.value) return
  const modal = props.channel.has_password
    ? disablePasswordModal
    : passwordModal
  modal.value.show()
}
</script>
