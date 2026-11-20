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
      :default-values="builder"
      @values-changed="onValuesChanged"
    >
      <template #head-html>
        <FormGroup class="margin-bottom-2" :error="htmlState.error" small-label>
          <template #label>
            {{ $t('customCodeSettingForm.customHtml') }}
          </template>
          <CodeEditor
            :model-value="htmlState.draft ?? builder.head_html"
            language="html"
            :placeholder="$t('customCodeSettingForm.customHtmlPlaceholder')"
            :modal-title="$t('customCodeSettingForm.customHtml')"
            :error-message="htmlErrorMessage"
            @update:model-value="onHtmlChanged"
            @blur="autosaveHtml.flush()"
          />
          <template v-if="headHtmlHiddenInPreview" #helper>
            {{ $t('customCodeSettingForm.customHtmlNotInPreview') }}
          </template>
          <template #error>
            <span role="alert">{{ htmlErrorMessage }}</span>
          </template>
        </FormGroup>
      </template>
    </CustomCodeSettingForm>
  </div>
</template>

<script>
import { reactive } from 'vue'
import _ from 'lodash'
import ApplicationUntrustedContentAlert from '@baserow/modules/core/components/application/ApplicationUntrustedContentAlert'
import CodeEditor from '@baserow/modules/core/components/CodeEditor.vue'
import { clone, isSubObject } from '@baserow/modules/core/utils/object'
import CustomCodeSettingForm from '@baserow_enterprise/components/builder/CustomCodeSettingForm.vue'
import { previewSharesEditorHostname } from '@baserow_enterprise/utils/builderHeadHtml'

const htmlDrafts = new WeakMap()
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
    // Keep unsaved HTML when the settings modal closes.
    let htmlState = htmlDrafts.get(this.builder)
    if (!htmlState) {
      htmlState = reactive({
        draft: null,
        error: false,
        pending: Promise.resolve(),
      })
      htmlDrafts.set(this.builder, htmlState)
    }
    return { htmlState }
  },
  computed: {
    headHtmlHiddenInPreview() {
      return previewSharesEditorHostname(this.$config.public)
    },
    htmlErrorMessage() {
      return this.htmlState.error
        ? this.$t('customCodeSettingForm.customHtmlSaveError')
        : ''
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
    async updateApplication(values) {
      const form = this.$refs.settingsForm
      if (!form?.isFormValid(true) || isSubObject(this.builder, values)) {
        return
      }

      try {
        await this.$store.dispatch('application/update', {
          application: this.builder,
          values,
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
      this.htmlState.draft = html
      this.htmlState.error = false
      this.autosaveHtml(html)
    },
    saveHtml(html) {
      const state = this.htmlState
      const builder = this.builder
      state.pending = state.pending.then(async () => {
        if (state.draft !== html) return
        try {
          if (builder.head_html !== html) {
            await this.$store.dispatch('application/update', {
              application: builder,
              values: { head_html: html },
            })
          }
          if (state.draft === html) {
            state.error = builder.head_html !== html
            if (!state.error) {
              state.draft = null
            }
          }
        } catch (error) {
          if (state.draft === html) state.error = true
          error.handler?.handled?.()
        }
      })
      return state.pending
    },
  },
}
</script>
