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
        <FormGroup class="margin-bottom-2" :error="htmlSaveError" small-label>
          <template #label>
            {{ $t('customCodeSettingForm.customHtml') }}
          </template>
          <CodeEditor
            :model-value="htmlDraft ?? savedHtml"
            language="html"
            :placeholder="$t('customCodeSettingForm.customHtmlPlaceholder')"
            :modal-title="$t('customCodeSettingForm.customHtml')"
            :error-message="htmlErrorMessage"
            @update:model-value="onHtmlChanged"
            @blur="autosaveHtml.flush()"
          />
          <template #error>
            <span role="alert">{{ htmlErrorMessage }}</span>
          </template>
        </FormGroup>
      </template>
    </CustomCodeSettingForm>
  </div>
</template>

<script>
import _ from 'lodash'
import ApplicationUntrustedContentAlert from '@baserow/modules/core/components/application/ApplicationUntrustedContentAlert'
import CodeEditor from '@baserow/modules/core/components/CodeEditor.vue'
import { clone, isSubObject } from '@baserow/modules/core/utils/object'
import CustomCodeSettingForm from '@baserow_enterprise/components/builder/CustomCodeSettingForm.vue'

const pendingCodeUpdates = new WeakMap()
const AUTOSAVE_DELAY = 500

export default {
  name: 'CustomCodeSetting',
  components: {
    CustomCodeSettingForm,
    ApplicationUntrustedContentAlert,
    CodeEditor,
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
  data() {
    return {
      htmlDraft: null,
      htmlSaveError: false,
    }
  },
  computed: {
    htmlErrorMessage() {
      return this.htmlSaveError
        ? this.$t('customCodeSettingForm.customHtmlSaveError')
        : ''
    },
    savedHtml() {
      return this.builder.custom_code?.html ?? ''
    },
    autosaveValues() {
      const { css = '', js = '' } = this.builder.custom_code ?? {}
      return { custom_code: { css, js }, scripts: this.builder.scripts }
    },
  },
  created() {
    this.autosaveSettings = _.debounce(this.updateApplication, AUTOSAVE_DELAY)
    this.autosaveHtml = _.debounce(this.saveHtml, AUTOSAVE_DELAY)
  },
  beforeUnmount() {
    this.autosaveSettings.cancel()
    this.autosaveHtml.flush()
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
    onValuesChanged(values) {
      this.autosaveSettings(clone(values))
    },
    onHtmlChanged(html) {
      this.htmlDraft = html
      this.htmlSaveError = false
      this.autosaveHtml(html)
    },
    async saveHtml(html) {
      try {
        await this.queueCodeUpdate(async () => {
          if (this.htmlDraft !== html) {
            return
          }
          if (this.savedHtml !== html) {
            await this.$store.dispatch('application/update', {
              application: this.builder,
              values: { custom_code: { html } },
            })
          }
          if (this.htmlDraft === html) {
            this.htmlSaveError = this.savedHtml !== html
            if (!this.htmlSaveError) {
              this.htmlDraft = null
            }
          }
        })
      } catch (error) {
        if (this.htmlDraft === html) {
          this.htmlSaveError = true
        }
        error.handler?.handled?.()
      }
    },
  },
}
</script>
