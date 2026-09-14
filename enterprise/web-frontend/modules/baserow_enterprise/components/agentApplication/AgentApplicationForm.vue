<template>
  <form class="agent-create" @submit.prevent="submit">
    <template v-if="step === 1">
      <FormGroup
        :error="v$.values.name.$error"
        small-label
        :label="$t('agentCreate.nameLabel')"
        required
        class="margin-bottom-2"
      >
        <FormInput
          ref="name"
          v-model="v$.values.name.$model"
          size="large"
          :placeholder="$t('agentCreate.namePlaceholder')"
          :error="v$.values.name.$error"
          @focus.once="$event.target.select()"
          @blur="v$.values.name.$touch"
        >
        </FormInput>
        <template #error>
          {{ $t('error.requiredField') }}
        </template>
      </FormGroup>
      <FormGroup small-label class="margin-bottom-2">
        <template #label>
          <span class="agent-create__label-row">
            <span>{{ $t('agentCreate.whatLabel') }}</span>
            <Badge color="cyan" size="small">
              <i class="iconoir-sparks"></i>
              {{ $t('agentCreate.kumaBadge') }}
            </Badge>
          </span>
        </template>
        <FormTextarea
          v-model="values.description"
          :rows="5"
          :placeholder="$t('agentCreate.whatPlaceholder')"
        ></FormTextarea>
      </FormGroup>
      <div class="agent-create__templates">
        <a
          v-for="template in templates"
          :key="template.key"
          class="agent-create__template"
          @click.prevent="applyTemplate(template)"
        >
          <i :class="template.icon"></i>
          {{ template.label }}
        </a>
      </div>
      <div class="actions actions--right actions--gap margin-bottom-0">
        <Button tag="a" type="secondary" size="large" @click="$emit('hidden')">
          {{ $t('agentCreate.cancel') }}
        </Button>
        <Button
          tag="a"
          type="primary"
          size="large"
          :loading="drafting"
          :disabled="drafting"
          @click="continueToReview"
        >
          {{ $t('agentCreate.continue') }}
        </Button>
      </div>
    </template>
    <template v-else>
      <div class="agent-create__step-title">
        <a class="agent-create__back" @click.prevent="step = 1">
          <i class="iconoir-nav-arrow-left"></i>
        </a>
        <span>{{ $t('agentCreate.reviewTitle') }}</span>
      </div>
      <p class="agent-create__intro">{{ $t('agentCreate.reviewIntro') }}</p>
      <FormGroup
        small-label
        :label="$t('agentCreate.instructionsLabel')"
        class="margin-bottom-2"
      >
        <FormTextarea
          v-model="values.instructions"
          :rows="8"
          :placeholder="$t('agentInstructions.placeholder')"
        ></FormTextarea>
      </FormGroup>
      <FormGroup
        small-label
        :label="$t('agentCreate.whenItRuns')"
        class="margin-bottom-2"
      >
        <Dropdown
          v-model="values.run_mode"
          :show-search="false"
          :fixed-items="true"
        >
          <DropdownItem
            v-for="option in runModes"
            :key="option.value"
            :name="option.name"
            :value="option.value"
            :icon="option.icon"
            :description="option.description"
          />
        </Dropdown>
      </FormGroup>
      <FormGroup
        small-label
        :label="$t('agentCreate.actsAs')"
        class="margin-bottom-2"
      >
        <Dropdown
          v-model="identityChoice"
          :show-search="false"
          :fixed-items="true"
          :disabled="loadingIdentities"
        >
          <DropdownItem
            v-if="canCreateIdentity"
            :name="$t('agentCreate.newIdentity', { name: values.name })"
            value="new"
            icon="baserow-icon-agent"
            :description="$t('agentCreate.newIdentityDescription')"
          />
          <DropdownItem
            v-for="identity in identities"
            :key="identity.id"
            :name="identity.name"
            :value="identity.id"
            icon="baserow-icon-agent"
            :description="$t('agentCreate.existingIdentityDescription')"
          />
          <DropdownItem
            :name="$t('agentCreate.noAccess')"
            value="none"
            icon="iconoir-prohibition"
            :description="$t('agentCreate.noAccessDescription')"
          />
        </Dropdown>
      </FormGroup>
      <FormGroup
        small-label
        :label="$t('agentCreate.permissions')"
        :helper-text="$t('agentCreate.permissionsHint')"
        class="margin-bottom-2"
      >
        <Dropdown
          v-model="values.permissions"
          :show-search="false"
          :fixed-items="true"
          :disabled="identityChoice === 'none'"
        >
          <DropdownItem
            v-for="option in permissionPresets"
            :key="option.value"
            :name="option.name"
            :value="option.value"
            :description="option.description"
          />
        </Dropdown>
      </FormGroup>
      <FormGroup
        small-label
        :label="$t('agentCreate.extras')"
        class="margin-bottom-2"
      >
        <div class="agent-create__extra">
          <i class="agent-create__extra-icon iconoir-globe"></i>
          <span class="agent-create__extra-text">
            <span class="agent-create__extra-title">
              {{ $t('agentCreate.webSearch') }}
            </span>
            <span class="agent-create__extra-description">
              {{ $t('agentCreate.webSearchDescription') }}
            </span>
          </span>
          <SwitchInput v-model="values.web_search" small></SwitchInput>
        </div>
      </FormGroup>
      <div class="actions agent-create__actions">
        <span class="agent-create__note">{{ $t('agentCreate.note') }}</span>
        <Button tag="a" type="secondary" size="large" @click="$emit('hidden')">
          {{ $t('agentCreate.cancel') }}
        </Button>
        <Button
          type="primary"
          size="large"
          :loading="loading"
          :disabled="loading"
        >
          {{ $t('agentCreate.create') }}
        </Button>
      </div>
    </template>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import { notifyIf } from '@baserow/modules/core/utils/error'
import AgentService from '@baserow/modules/core/services/agent'
import AgentApplicationService from '@baserow_enterprise/services/agentApplication'

const TEMPLATES = [
  { key: 'invest', icon: 'iconoir-globe' },
  { key: 'founders', icon: 'iconoir-mail' },
  { key: 'tickets', icon: 'iconoir-db' },
  { key: 'hiring', icon: 'iconoir-clock' },
]

export default {
  name: 'AgentApplicationForm',
  mixins: [form],
  props: {
    defaultName: {
      type: String,
      required: false,
      default: '',
    },
    loading: {
      type: Boolean,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  emits: ['submitted', 'hidden'],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      step: 1,
      drafting: false,
      identities: [],
      loadingIdentities: false,
      identityChoice: 'none',
      values: {
        name: this.defaultName,
        description: '',
        instructions: '',
        run_mode: 'chat',
        permissions: 'ask_first',
        web_search: false,
      },
    }
  },
  computed: {
    templates() {
      return TEMPLATES.map((template) => ({
        ...template,
        label: this.$t(`agentCreate.template_${template.key}`),
        description: this.$t(`agentCreate.template_${template.key}Description`),
        name: this.$t(`agentCreate.template_${template.key}Name`),
      }))
    },
    runModes() {
      return [
        {
          value: 'chat',
          icon: 'iconoir-chat-bubble-empty',
          name: this.$t('agentCreate.runChatOnly'),
          description: this.$t('agentCreate.runChatOnlyDescription'),
        },
        {
          value: 'daily',
          icon: 'iconoir-timer',
          name: this.$t('agentCreate.runDaily'),
          description: this.$t('agentCreate.runScheduleDescription'),
        },
        {
          value: 'weekly',
          icon: 'iconoir-timer',
          name: this.$t('agentCreate.runWeekly'),
          description: this.$t('agentCreate.runScheduleDescription'),
        },
      ]
    },
    permissionPresets() {
      return ['read_only', 'ask_first', 'free'].map((value) => ({
        value,
        name: this.$t(`agentCreate.permissions_${value}`),
        description: this.$t(`agentCreate.permissions_${value}Description`),
      }))
    },
    // The workspace object of the create modal doesn't carry the permission
    // data; the full one comes from the store.
    fullWorkspace() {
      return this.$store.getters['workspace/get'](this.workspace.id)
    },
    canCreateIdentity() {
      return (
        this.fullWorkspace !== undefined &&
        this.$hasPermission(
          'agent.create',
          this.fullWorkspace,
          this.fullWorkspace.id
        )
      )
    },
  },
  mounted() {
    this.$refs.name?.focus()
  },
  validations() {
    return {
      values: {
        name: { required },
      },
    }
  },
  methods: {
    applyTemplate(template) {
      this.values.description = template.description
      if (this.values.name === '' || this.values.name === this.defaultName) {
        this.values.name = template.name
      }
    },
    async continueToReview() {
      this.v$.$touch()
      if (this.v$.$invalid) {
        return
      }
      this.drafting = true
      try {
        await Promise.all([this.draftInstructions(), this.fetchIdentities()])
        this.identityChoice = this.canCreateIdentity ? 'new' : 'none'
        this.step = 2
      } finally {
        this.drafting = false
      }
    },
    async draftInstructions() {
      const description = this.values.description.trim()
      if (description === '' || this.values.instructions !== '') {
        return
      }
      try {
        const { data } = await AgentApplicationService(
          this.$client
        ).draftInstructions(this.workspace.id, {
          name: this.values.name,
          description,
        })
        this.values.instructions = data.instructions
      } catch (error) {
        // Drafting is a convenience; the user can still write the
        // instructions by hand on the next step.
        notifyIf(error, 'application')
        this.values.instructions = description
      }
    },
    async fetchIdentities() {
      this.loadingIdentities = true
      try {
        const { data } = await AgentService(this.$client).list(
          this.workspace.id
        )
        this.identities = data.results
      } catch {
        this.identities = []
      } finally {
        this.loadingIdentities = false
      }
    },
    getFormValues() {
      const values = {
        name: this.values.name,
        description: this.values.description,
        instructions: this.values.instructions,
        run_mode: this.values.run_mode,
        web_search: this.values.web_search,
      }
      if (this.identityChoice === 'new') {
        values.create_identity = true
      } else if (this.identityChoice !== 'none') {
        values.agent_identity_id = this.identityChoice
      }
      if (this.identityChoice !== 'none') {
        values.permissions = this.values.permissions
      }
      return values
    },
  },
}
</script>
