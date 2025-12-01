<template>
  <div>
    <h2 class="box__title">{{ $t('generativeAIWorkspaceSettings.title') }}</h2>
    <p>{{ $t('generativeAIWorkspaceSettings.description') }}</p>
    <Error :error="error"></Error>
    <Alert v-if="success" ref="success" type="success">
      <template #title>{{
        $t('generativeAIWorkspaceSettings.changedTitle')
      }}</template>
      <p>{{ $t('generativeAIWorkspaceSettings.changedDescription') }}</p>
    </Alert>
    <div v-if="fetchLoading">
      <div class="loading"></div>
    </div>
    <form v-else @submit.prevent="updateSettings">
      <div
        v-for="[type, modelType] in modelTypes"
        :key="type"
        class="margin-top-3"
      >
        <Expandable card>
          <template #header="{ toggle, expanded }">
            <div class="flex flex-100 justify-content-space-between">
              <div>
                <div class="margin-bottom-1">
                  <strong>{{ modelType.getName() }}</strong>
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
                {{
                  isEnabled(type) ? $t('common.enabled') : $t('common.disabled')
                }}
              </div>
            </div>
          </template>
          <template #default>
            <FormGroup
              v-for="setting in modelType.getSettings()"
              :key="setting.key"
              small-label
              :label="setting.label"
              :error="v$.settings[type][setting.key].$error"
              :error-message="
                getSettingErrorMessage(v$.settings[type][setting.key])
              "
              required
              class="margin-bottom-2"
            >
              <FormInput
                v-model.trim="v$.settings[type][setting.key].$model"
                :error="v$.settings[type][setting.key].$error"
                :placeholder="setting.placeholder || null"
              />

              <template v-if="setting.description" #helper>
                <MarkdownIt :content="setting.description" />
              </template>
            </FormGroup>
          </template>
        </Expandable>
      </div>
      <div class="actions actions--right">
        <Button
          :disabled="updateLoading || v$.$invalid || !v$.$anyDirty"
          :loading="updateLoading"
          icon="iconoir-edit-pencil"
        >
          {{ $t('generativeAIWorkspaceSettings.submitButton') }}
        </Button>
      </div>
    </form>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import error from '@baserow/modules/core/mixins/error'
import WorkspaceService from '@baserow/modules/core/services/workspace'

export default {
  mixins: [error],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      fetchLoading: false,
      updateLoading: false,
      success: false,
      settings: {},
    }
  },
  computed: {
    modelTypes() {
      return this.$registry
        .getOrderedList('generativeAIModel')
        .filter((modelType) => modelType.getSettings() !== null)
        .map((modelType) => [modelType.getType(), modelType])
    },
  },
  async mounted() {
    await this.fetchSettings()
  },
  methods: {
    async fetchSettings() {
      this.fetchLoading = true
      try {
        const { data } = await WorkspaceService(
          this.$client
        ).getGenerativeAISettings(this.workspace.id)

        // Initialize the settings object with the backend values.
        for (const [type, modelType] of this.modelTypes) {
          if (this.settings[type] === undefined) {
            this.$set(this.settings, type, {})
          }
          if (data[type] === undefined) {
            continue
          }
          for (const setting of modelType.getSettings()) {
            const value = data[type][setting.key]
            const parse = setting.parse || ((value) => value)
            this.$set(this.settings[type], setting.key, parse(value))
          }
        }
      } catch (error) {
        this.handleError(error)
      } finally {
        this.fetchLoading = false
      }
    },
    async updateSettings() {
      this.v$.$touch()

      if (this.v$.$invalid) {
        return
      }

      this.updateLoading = true
      this.hideError()

      const settings = {}
      for (const [type, modelType] of this.modelTypes) {
        settings[type] = {}
        for (const setting of modelType.getSettings()) {
          const value = this.settings[type][setting.key]
          if (value === undefined) {
            continue
          }
          const serialize = setting.serialize || ((value) => value)
          settings[type][setting.key] = serialize(value)
        }
      }

      try {
        const { data } = await WorkspaceService(
          this.$client
        ).updateGenerativeAISettings(this.workspace.id, settings)
        // Force update the workspace enabled models so that the changes are reflected
        // immediately.
        await this.$store.dispatch('workspace/forceUpdate', {
          workspace: this.workspace,
          values: data,
        })

        this.success = true
        this.$nextTick(() => {
          this.$refs.success.$el.scrollIntoView({ behavior: 'smooth' })
        })
      } catch (error) {
        this.handleError(error)
      } finally {
        this.updateLoading = false
      }
    },
    isEnabled(typeName) {
      const enabled = this.workspace.generative_ai_models_enabled || {}
      return (
        Object.prototype.hasOwnProperty.call(enabled, typeName) &&
        enabled[typeName].length > 0
      )
    },
    getSettingErrorMessage(object) {
      if (!object.$error || !object.$errors || object.$errors.length === 0) {
        return null
      }
      return object.$errors.map((error) => error.$message).join(' ')
    },
  },
  validations() {
    const settings = this.modelTypes.reduce((acc, [type, modelType]) => {
      acc[type] = modelType.getSettings().reduce((acc, setting) => {
        acc[setting.key] = setting.validations || {}
        return acc
      }, {})
      return acc
    }, {})
    return { settings }
  },
}
</script>
