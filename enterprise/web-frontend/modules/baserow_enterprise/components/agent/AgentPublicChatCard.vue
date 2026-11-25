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
      <div class="agent-public-chat-card__section">
        <FormSection :title="$t('agentChannels.appearance')">
          <FormGroup
            horizontal-narrow
            small-label
            required
            class="margin-bottom-2"
            :label="$t('agentChannels.font')"
          >
            <FontFamilySelector
              class="agent-public-chat-card__font"
              :model-value="channel.font"
              :disabled="!canEdit"
              @update:model-value="saveDraft('font', $event)"
            />
          </FormGroup>
          <FormGroup
            horizontal-narrow
            small-label
            required
            class="margin-bottom-2"
            :label="$t('agentChannels.accentColor')"
          >
            <div
              class="agent-public-chat-card__color flex align-items-center"
              :inert="!canEdit || null"
            >
              <ColorInput
                :model-value="shownColor('accent_color')"
                :allow-opacity="false"
                small
                @update:model-value="pickColor('accent_color', $event)"
              />
              <ButtonText
                v-if="canEdit && channel.accent_color"
                size="small"
                button-type="button"
                @click="resetColor('accent_color')"
              >
                {{ $t('agentChannels.resetColor') }}
              </ButtonText>
            </div>
          </FormGroup>
          <FormGroup
            horizontal-narrow
            small-label
            required
            class="margin-bottom-2"
            :label="$t('agentChannels.background')"
          >
            <SegmentControl
              class="agent-public-chat-card__background"
              size="small"
              :segments="backgroundSegments"
              :active-index="BACKGROUNDS.indexOf(channel.background)"
              :disabled="!canEdit"
              @update:active-index="
                saveDraft('background', BACKGROUNDS[$event])
              "
            />
          </FormGroup>
          <FormGroup
            v-if="channel.background === PUBLIC_CHAT_BACKGROUND.PLAIN"
            horizontal-narrow
            small-label
            required
            class="margin-bottom-2"
            :label="$t('agentChannels.backgroundColor')"
          >
            <div
              class="agent-public-chat-card__color flex align-items-center"
              :inert="!canEdit || null"
            >
              <ColorInput
                :model-value="shownColor('background_color')"
                :allow-opacity="false"
                small
                @update:model-value="pickColor('background_color', $event)"
              />
              <ButtonText
                v-if="canEdit && channel.background_color"
                size="small"
                button-type="button"
                @click="resetColor('background_color')"
              >
                {{ $t('agentChannels.resetColor') }}
              </ButtonText>
            </div>
          </FormGroup>
          <SwitchInput
            class="agent-public-chat-card__powered-by"
            small
            role="switch"
            :tabindex="canEdit ? 0 : -1"
            :aria-checked="channel.show_powered_by"
            :aria-disabled="!canEdit"
            :model-value="channel.show_powered_by"
            :disabled="!canEdit"
            @update:model-value="saveDraft('show_powered_by', $event)"
            @keydown.enter.prevent="togglePoweredBy"
            @keydown.space.prevent="togglePoweredBy"
          >
            <span>{{ $t('agentChannels.showPoweredBy') }}</span>
          </SwitchInput>
        </FormSection>
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
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useNuxtApp } from '#app'
import { useI18n } from 'vue-i18n'
import debounce from 'lodash/debounce'
import Icon from '@baserow/modules/core/components/Icon'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import ColorInput from '@baserow/modules/core/components/ColorInput'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor'
import FontFamilySelector from '@baserow/modules/builder/components/FontFamilySelector'
import { copyToClipboard } from '@baserow/modules/core/utils/clipboard'
import AgentPublicChatPasswordModal from '@baserow_enterprise/components/agent/AgentPublicChatPasswordModal'
import AgentPublicChatDisablePasswordModal from '@baserow_enterprise/components/agent/AgentPublicChatDisablePasswordModal'
import { PUBLIC_CHAT_BACKGROUND } from '@baserow_enterprise/composables/useAgentChannels'

const TITLE_MAX_LENGTH = 160
const WELCOME_TEXT_MAX_LENGTH = 2000
const BACKGROUNDS = Object.values(PUBLIC_CHAT_BACKGROUND)
const COLOR_SAVE_DELAY_MS = 400
// What the public page shows for a blank colour: Baserow's blue and white.
const DEFAULT_COLORS = { accent_color: '#5190ef', background_color: '#ffffff' }

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

const backgroundSegments = computed(() => [
  { label: t('agentChannels.backgroundPlain') },
  { label: t('agentChannels.backgroundGradient') },
])
const colorDrafts = {
  accent_color: draftOf('accent_color'),
  background_color: draftOf('background_color'),
}
const colorSaves = Object.fromEntries(
  Object.keys(colorDrafts).map((field) => [
    field,
    debounce((value) => saveDraft(field, value), COLOR_SAVE_DELAY_MS),
  ])
)

const shownColor = (field) => colorDrafts[field].value || DEFAULT_COLORS[field]

/** The picker reports every step of a drag; only where it stops is saved. */
function pickColor(field, value) {
  colorDrafts[field].value = value.toLowerCase()
  colorSaves[field](colorDrafts[field].value)
}

function resetColor(field) {
  colorSaves[field].cancel()
  colorDrafts[field].value = ''
  saveDraft(field, '')
}

function togglePoweredBy() {
  saveDraft('show_powered_by', !props.channel.show_powered_by)
}

onBeforeUnmount(() => Object.values(colorSaves).forEach((save) => save.flush()))

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
