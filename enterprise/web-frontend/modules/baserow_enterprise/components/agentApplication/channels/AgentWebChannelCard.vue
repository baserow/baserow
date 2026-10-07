<template>
  <div>
    <FormGroup
      v-if="isWebsite"
      small-label
      :label="$t('agentChannels.embedCodeLabel')"
      :helper-text="$t('agentChannels.embedCodeHelp')"
      class="margin-bottom-2"
    >
      <div class="agent-configuration__channel-url">
        <pre class="agent-configuration__channel-url-box">{{ embedCode }}</pre>
        <a
          class="agent-configuration__channel-url-copy"
          :title="$t('agentChannels.copyCode')"
          @click="copyText(embedCode)"
        >
          <i class="iconoir-copy"></i>
          <Copied ref="copied"></Copied>
        </a>
      </div>
      <a
        class="agent-configuration__channel-preview-link"
        :href="publicUrl"
        target="_blank"
        rel="noopener"
      >
        <i class="iconoir-open-new-window"></i>
        {{ $t('agentChannels.previewChat') }}
      </a>
    </FormGroup>
    <FormGroup
      v-else
      small-label
      :label="$t('agentChannels.publicLinkLabel')"
      :helper-text="$t('agentChannels.publicLinkHelp')"
      class="margin-bottom-2"
    >
      <div class="agent-configuration__channel-url">
        <div class="agent-configuration__channel-url-box">
          {{ publicUrl }}
        </div>
        <a
          class="agent-configuration__channel-url-copy"
          :title="$t('agentChannels.copyUrl')"
          @click="copyText(publicUrl)"
        >
          <i class="iconoir-copy"></i>
          <Copied ref="copied"></Copied>
        </a>
      </div>
      <ButtonText
        v-if="canUpdate"
        icon="iconoir-refresh"
        class="margin-top-1"
        @click="$refs.rotateModal.show()"
      >
        {{ $t('agentChannels.rotateLink') }}
      </ButtonText>
    </FormGroup>
    <div
      v-if="!isWebsite"
      class="agent-configuration__switch-row agent-configuration__switch-row--plain"
    >
      <i class="agent-configuration__switch-icon iconoir-lock"></i>
      <div class="agent-configuration__switch-text">
        <div class="agent-configuration__switch-title">
          {{ $t('agentChannels.passwordProtected') }}
        </div>
        <div class="agent-configuration__switch-description">
          {{ $t('agentChannels.passwordProtectedDescription') }}
        </div>
      </div>
      <SwitchInput
        small
        :value="!!channel.config.has_password"
        :disabled="!canUpdate"
        @input="onPasswordToggle"
      ></SwitchInput>
    </div>
    <FormGroup
      small-label
      :label="$t('agentChannels.titleLabel')"
      class="margin-bottom-2 margin-top-2"
    >
      <FormInput
        v-model="draft.title"
        :disabled="!canUpdate"
        :placeholder="agentName"
        @input="onConfigChanged"
      ></FormInput>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('agentChannels.welcomeTextLabel')"
      :helper-text="$t('agentChannels.welcomeTextHelp')"
      class="margin-bottom-2"
    >
      <FormTextarea
        v-model="draft.welcomeText"
        :rows="3"
        :disabled="!canUpdate"
        :placeholder="$t('agentChannels.welcomeTextPlaceholder')"
        @input="onConfigChanged"
      ></FormTextarea>
    </FormGroup>
    <template v-if="isWebsite">
      <FormGroup
        small-label
        :label="$t('agentChannels.buttonTextLabel')"
        class="margin-bottom-2"
      >
        <FormInput
          v-model="draft.buttonText"
          :disabled="!canUpdate"
          :placeholder="$t('agentChannels.buttonTextPlaceholder')"
          @input="onConfigChanged"
        ></FormInput>
      </FormGroup>
      <div class="agent-configuration__field-row margin-bottom-2">
        <FormGroup small-label :label="$t('agentChannels.buttonColorLabel')">
          <ColorInput
            v-model="draft.buttonColor"
            small
            :allow-opacity="false"
            :disabled="!canUpdate"
            @update:model-value="onConfigChanged"
          ></ColorInput>
        </FormGroup>
        <FormGroup small-label :label="$t('agentChannels.buttonPositionLabel')">
          <Dropdown
            v-model="draft.buttonPosition"
            :show-search="false"
            :fixed-items="true"
            :disabled="!canUpdate"
            @update:model-value="onConfigChanged"
          >
            <DropdownItem
              v-for="option in buttonPositions"
              :key="option.value"
              :name="option.name"
              :value="option.value"
            />
          </Dropdown>
        </FormGroup>
      </div>
    </template>
    <div class="agent-configuration__hint">
      {{
        isWebsite
          ? $t('agentChannels.websiteHint')
          : $t('agentChannels.webHint')
      }}
    </div>
    <Modal ref="rotateModal" small>
      <h2 class="box__title">{{ $t('agentChannels.rotateLinkTitle') }}</h2>
      <p>{{ $t('agentChannels.rotateLinkText') }}</p>
      <div class="actions actions--right actions--gap margin-bottom-0">
        <Button type="secondary" @click="$refs.rotateModal.hide()">
          {{ $t('agentChannels.cancel') }}
        </Button>
        <Button type="danger" :loading="rotating" @click="rotateLink">
          {{ $t('agentChannels.rotateLinkConfirm') }}
        </Button>
      </div>
    </Modal>
    <Modal ref="passwordModal" small @hidden="passwordDraft = ''">
      <h2 class="box__title">{{ $t('agentChannels.passwordTitle') }}</h2>
      <form @submit.prevent="savePassword">
        <FormGroup
          small-label
          :label="$t('agentChannels.passwordLabel')"
          required
          class="margin-bottom-2"
        >
          <FormInput
            ref="passwordInput"
            v-model="passwordDraft"
            type="password"
            :placeholder="$t('agentChannels.passwordPlaceholder')"
          ></FormInput>
        </FormGroup>
        <div class="actions actions--right actions--gap margin-bottom-0">
          <Button tag="a" type="secondary" @click="$refs.passwordModal.hide()">
            {{ $t('agentChannels.cancel') }}
          </Button>
          <Button
            type="primary"
            :loading="savingPassword"
            :disabled="passwordDraft.trim() === ''"
          >
            {{ $t('agentChannels.passwordSave') }}
          </Button>
        </div>
      </form>
    </Modal>
  </div>
</template>

<script>
import agentChannelCard from '@baserow_enterprise/mixins/agentChannelCard'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import { notifyIf } from '@baserow/modules/core/utils/error'

const BUTTON_POSITIONS = [
  'bottom-right',
  'bottom-left',
  'top-right',
  'top-left',
]

export default {
  name: 'AgentWebChannelCard',
  mixins: [agentChannelCard],
  data() {
    return { rotating: false, passwordDraft: '', savingPassword: false }
  },
  computed: {
    isWebsite() {
      return this.channel.type === 'website'
    },
    buttonPositions() {
      return BUTTON_POSITIONS.map((value) => ({
        value,
        name: this.$t(`agentChannels.position_${value}`),
      }))
    },
    embedCode() {
      // Split so the closing tag can't end this component's own script
      // block when the template is compiled.
      return (
        `<script src="${this.channel.config.embed_script_url}" async></scr` +
        `ipt>`
      )
    },
    publicUrl() {
      return (
        this.$config.public.baserowEmbeddedShareUrl +
        this.$router.resolve({
          name: 'agent-public-chat',
          params: { slug: this.channel.config.slug },
        }).href
      )
    },
  },
  methods: {
    draftConfigValues() {
      const values = {
        title: this.draft.title,
        welcome_text: this.draft.welcomeText,
      }
      if (this.isWebsite) {
        values.button_text = this.draft.buttonText
        values.button_color = this.draft.buttonColor
        values.button_position = this.draft.buttonPosition
      }
      return values
    },
    copyText(text) {
      copyToClipboard(text)
      this.$refs.copied?.show()
    },
    async rotateLink() {
      this.rotating = true
      try {
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/rotateChannelSlug`,
          { channelId: this.channel.id }
        )
        this.$refs.rotateModal.hide()
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.rotating = false
      }
    },
    async onPasswordToggle(enabled) {
      if (enabled) {
        this.$refs.passwordModal.show()
        this.$nextTick(() => this.$refs.passwordInput?.focus())
        return
      }
      await this.updateChannel({ config: { password: '' } })
    },
    async savePassword() {
      if (this.passwordDraft.trim() === '') {
        return
      }
      this.savingPassword = true
      try {
        await this.updateChannel({ config: { password: this.passwordDraft } })
        this.$refs.passwordModal.hide()
      } finally {
        this.savingPassword = false
      }
    },
  },
}
</script>
