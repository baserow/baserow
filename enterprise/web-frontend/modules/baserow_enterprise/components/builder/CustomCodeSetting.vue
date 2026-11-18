<template>
  <div>
    <ApplicationUntrustedContentAlert
      :content-owner="builder"
      :compact="false"
      :can-trust="
        $hasPermission('application.update', builder, builder.workspace.id)
      "
      :trust-content="trustContent"
      :message="$t('builderUntrustedContent.warning')"
    />
    <CustomCodeSettingForm
      ref="settingsForm"
      :default-values="autosaveValues"
      @values-changed="onValuesChanged"
    >
      <template #head-html>
        <form @submit.prevent="saveHtml">
          <FormGroup
            class="margin-bottom-2"
            :helper-text="$t('customCodeSettingForm.customHtmlHelp')"
            :error="htmlSaveError"
            small-label
          >
            <template #label>
              <label :for="htmlInputId">
                {{ $t('customCodeSettingForm.customHtml') }}
              </label>
            </template>
            <FormTextarea
              :id="htmlInputId"
              v-model="htmlDraft"
              :rows="6"
              :disabled="savingHtml"
              :error="htmlSaveError"
              :aria-invalid="htmlSaveError"
              :aria-describedby="htmlSaveError ? htmlErrorId : undefined"
              spellcheck="false"
            />
            <template #error>
              <span :id="htmlErrorId" role="alert">
                {{ $t('customCodeSettingForm.customHtmlSaveError') }}
              </span>
            </template>
          </FormGroup>
          <Button
            button-type="submit"
            type="secondary"
            :loading="savingHtml"
            :disabled="htmlDraft === savedHtml"
          >
            {{ $t('customCodeSettingForm.saveHtml') }}
          </Button>
        </form>
      </template>
    </CustomCodeSettingForm>
  </div>
</template>

<script>
import { useId } from 'vue'
import ApplicationUntrustedContentAlert from '@baserow/modules/core/components/application/ApplicationUntrustedContentAlert'
import FormTextarea from '@baserow/modules/core/components/FormTextarea'
import { clone, isSubObject } from '@baserow/modules/core/utils/object'
import CustomCodeSettingForm from '@baserow_enterprise/components/builder/CustomCodeSettingForm.vue'

const pendingCodeUpdates = new WeakMap()

export default {
  name: 'CustomCodeSetting',
  components: {
    CustomCodeSettingForm,
    ApplicationUntrustedContentAlert,
    FormTextarea,
  },
  provide() {
    return {
      builder: this.builder,
      mode: null,
    }
  },
  props: {
    builder: {
      type: Object,
      required: true,
    },
  },
  setup() {
    const htmlInputId = useId()
    return { htmlInputId, htmlErrorId: `${htmlInputId}-error` }
  },
  data() {
    return {
      debounceTimeout: null,
      htmlDraft: this.builder.custom_code?.html ?? '',
      savingHtml: false,
      htmlSaveError: false,
    }
  },
  computed: {
    savedHtml() {
      return this.builder.custom_code?.html ?? ''
    },
    autosaveValues() {
      const { css = '', js = '' } = this.builder.custom_code ?? {}
      return { custom_code: { css, js }, scripts: this.builder.scripts }
    },
  },
  watch: {
    savedHtml(html, previousHtml) {
      if (this.htmlDraft === previousHtml) {
        this.htmlDraft = html
      }
    },
    htmlDraft() {
      this.htmlSaveError = false
    },
  },
  beforeUnmount() {
    clearTimeout(this.debounceTimeout)
  },
  methods: {
    trustContent() {
      return this.$store.dispatch('application/update', {
        application: this.builder,
        values: { untrusted_content: false },
      })
    },
    queueCodeUpdate(update) {
      const application = this.builder
      const pending = pendingCodeUpdates.get(application) ?? Promise.resolve()
      // The API returns the entire custom_code object after each save.
      // Serialize updates so an older response cannot replace a newer save.
      const request = pending.then(update, update)
      pendingCodeUpdates.set(application, request)
      const clear = () => {
        if (pendingCodeUpdates.get(application) === request) {
          pendingCodeUpdates.delete(application)
        }
      }
      request.then(clear, clear)
      return request
    },
    async updateApplication(values) {
      const form = this.$refs.settingsForm
      if (!form?.isFormValid(true)) {
        return
      }

      try {
        await this.queueCodeUpdate(() => {
          if (!isSubObject(this.autosaveValues, values)) {
            return this.$store.dispatch('application/update', {
              application: this.builder,
              values,
            })
          }
        })
      } catch {
        const title = this.$t('generalSettings.cantUpdateApplicationTitle')
        const message = this.$t(
          'generalSettings.cantUpdateApplicationDescription'
        )
        this.$store.dispatch('toast/error', { title, message })
        if (
          this.$refs.settingsForm === form &&
          isSubObject(form.values, values)
        ) {
          form.reset()
        }
      }
    },
    onValuesChanged(newValues) {
      clearTimeout(this.debounceTimeout)
      const values = clone(newValues)
      this.debounceTimeout = setTimeout(() => {
        this.updateApplication(values)
      }, 500)
    },
    async saveHtml() {
      const html = this.htmlDraft
      if (this.savingHtml || html === this.savedHtml) {
        return
      }

      this.savingHtml = true
      this.htmlSaveError = false
      try {
        await this.queueCodeUpdate(() =>
          this.$store.dispatch('application/update', {
            application: this.builder,
            values: { custom_code: { html } },
          })
        )
        this.htmlSaveError = this.savedHtml !== html
      } catch (error) {
        this.htmlSaveError = true
        error.handler?.handled?.()
      } finally {
        this.savingHtml = false
      }
    },
  },
}
</script>
