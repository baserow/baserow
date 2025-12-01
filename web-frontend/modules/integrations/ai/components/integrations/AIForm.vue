<template>
  <div>
    <p class="margin-bottom-2">
      {{ $t('aiForm.description') }}
    </p>
    <Alert type="info-primary" class="margin-bottom-2">
      <template #title>{{ $t('aiForm.workspaceSettingsTitle') }}</template>
      <p>{{ $t('aiForm.workspaceSettingsDescription') }}</p>
    </Alert>

    <div
      v-for="providerType in availableProviders"
      :key="providerType.type"
      class="margin-bottom-3"
    >
      <Expandable card>
        <template #header="{ toggle, expanded }">
          <div class="flex flex-100 justify-content-space-between">
            <div>
              <div class="margin-bottom-1">
                <strong>{{ getProviderName(providerType.type) }}</strong>
              </div>
              <div>
                <a @click="toggle">
                  <template v-if="expanded">{{
                    $t('generativeAIWorkspaceSettings.hideSettings')
                  }}</template>
                  <template v-else>{{
                    $t('generativeAIWorkspaceSettings.openSettings')
                  }}</template>
                  <i
                    :class="
                      expanded
                        ? 'iconoir-nav-arrow-down'
                        : 'iconoir-nav-arrow-right'
                    "
                  />
                </a>
              </div>
            </div>
            <div>
              <Badge
                v-if="isProviderOverridden(providerType.type)"
                color="cyan"
                bold
              >
                {{ $t('aiForm.overridden') }}
              </Badge>
              <Badge v-else color="neutral">
                {{ $t('aiForm.inherited') }}
              </Badge>
            </div>
          </div>
        </template>
        <template #default>
          <Checkbox
            v-model="providerOverrides[providerType.type]"
            class="margin-bottom-2"
          >
            {{ $t('aiForm.overrideWorkspaceSettings') }}
          </Checkbox>

          <div v-if="providerOverrides[providerType.type]">
            <FormGroup
              v-for="setting in getProviderSettings(providerType.type)"
              :key="setting.key"
              small-label
              :label="setting.label"
              :error-message="
                v$.values.ai_settings?.[providerType.type]?.[setting.key]
                  ?.$errors[0]?.$message
              "
              :required="!setting.optional"
              class="margin-bottom-2"
            >
              <FormInput
                v-model.trim="
                  v$.values.ai_settings[providerType.type][setting.key].$model
                "
                @blur="
                  v$.values.ai_settings[providerType.type][setting.key].$touch()
                "
              />

              <template v-if="setting.description" #helper>
                <MarkdownIt :content="setting.description" />
              </template>
            </FormGroup>
          </div>
        </template>
      </Expandable>
    </div>
  </div>
</template>

<script>
import { required } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import { clone } from '@baserow/modules/core/utils/object'

export default {
  name: 'AIForm',
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      values: {
        ai_settings: {},
      },
      allowedValues: ['ai_settings'],
      providerOverrides: {},
    }
  },
  computed: {
    workspace() {
      return this.$store.getters['workspace/get'](this.application.workspace.id)
    },
    availableProviders() {
      // Get all registered generative AI model types
      const allProviders = this.$registry.getAll('generativeAIModel')
      return Object.keys(allProviders).map((type) => ({
        type,
      }))
    },
  },
  watch: {
    providerOverrides: {
      handler(newVal) {
        // When override is disabled, the provider can be removed from ai_settings so
        // make sure it does not accidentally try to use an empty object.
        Object.keys(newVal).forEach((providerType) => {
          if (!newVal[providerType]) {
            this.$delete(this.values.ai_settings, providerType)
          } else if (!this.values.ai_settings[providerType]) {
            const initialValues = this.parseProviderSettings(providerType)
            this.$set(this.values.ai_settings, providerType, initialValues)
          }
        })
      },
      deep: true,
    },
  },
  mounted() {
    this.availableProviders.forEach(({ type }) => {
      const isOverridden =
        this.values.ai_settings &&
        Object.prototype.hasOwnProperty.call(this.values.ai_settings, type)
      this.$set(this.providerOverrides, type, isOverridden)

      if (isOverridden) {
        const parsedValues = this.parseProviderSettings(
          type,
          this.values.ai_settings[type]
        )
        this.$set(this.values.ai_settings, type, parsedValues)
      }
    })
  },
  methods: {
    getProviderName(providerType) {
      const modelType = this.$registry.get('generativeAIModel', providerType)
      return modelType ? modelType.getName() : providerType
    },
    getProviderSettings(providerType) {
      const modelType = this.$registry.get('generativeAIModel', providerType)
      return modelType ? modelType.getSettings() : []
    },
    isProviderOverridden(providerType) {
      return this.providerOverrides[providerType] || false
    },
    parseProviderSettings(providerType, existingValues = null) {
      const settings = this.getProviderSettings(providerType)
      const parsedValues = {}
      settings.forEach((setting) => {
        const value = existingValues ? existingValues[setting.key] : ''
        const parse = setting.parse || ((value) => value)
        parsedValues[setting.key] = parse(value)
      })
      return parsedValues
    },
    getDefaultValues() {
      const aiSettings = this.defaultValues.ai_settings || {}
      return {
        ai_settings: clone(aiSettings),
      }
    },
    getFormValues() {
      // Serialize the ai_settings before submission, similar to
      // GenerativeAIWorkspaceSettings.vue
      const serializedSettings = {}
      this.availableProviders.forEach(({ type }) => {
        if (this.providerOverrides[type] && this.values.ai_settings[type]) {
          serializedSettings[type] = {}
          const settings = this.getProviderSettings(type)

          settings.forEach((setting) => {
            const value = this.values.ai_settings[type][setting.key]
            if (value !== undefined) {
              const serialize = setting.serialize || ((value) => value)
              serializedSettings[type][setting.key] = serialize(value)
            }
          })
        }
      })

      return {
        ai_settings: serializedSettings,
      }
    },
  },
  validations() {
    const validations = {
      values: {
        ai_settings: {},
      },
    }

    this.availableProviders.forEach(({ type }) => {
      if (this.providerOverrides[type]) {
        const settings = this.getProviderSettings(type)
        const providerValidations = {}
        settings.forEach((setting) => {
          providerValidations[setting.key] = setting.optional
            ? {}
            : { required }
        })

        validations.values.ai_settings[type] = providerValidations
      }
    })

    return validations
  },
}
</script>
