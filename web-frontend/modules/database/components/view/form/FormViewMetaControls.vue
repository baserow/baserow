<template>
  <div class="form-view__meta-controls">
    <SwitchInput
      small
      :value="view.receive_notification_on_submit"
      class="margin-bottom-3"
      @input="$emit('updated-form', { receive_notification_on_submit: $event })"
      >{{ $t('formSidebar.notifyUserOnSubmit') }}</SwitchInput
    >

    <FormGroup
      class="margin-bottom-3"
      small-label
      :label="$t('formViewMetaControls.whenSubmittedLabel')"
      required
    >
      <ul class="choice-items choice-items--inline">
        <li>
          <a
            class="choice-items__link"
            :class="{
              active: view.submit_action === 'MESSAGE',
              disabled: readOnly,
            }"
            @click="
              !readOnly &&
                view.submit_action !== 'MESSAGE' &&
                $emit('updated-form', { submit_action: 'MESSAGE' })
            "
            ><span>{{ $t('formViewMetaControls.showMessage') }}</span>
            <i
              v-if="view.submit_action === 'MESSAGE'"
              class="choice-items__icon-active iconoir-check-circle"
            ></i
          ></a>
        </li>
        <li>
          <a
            class="choice-items__link"
            :class="{
              active: view.submit_action === 'REDIRECT',
              disabled: readOnly,
            }"
            @click="
              !readOnly &&
                view.submit_action !== 'REDIRECT' &&
                $emit('updated-form', { submit_action: 'REDIRECT' })
            "
            ><span>{{ $t('formViewMetaControls.urlRedirect') }}</span>
            <i
              v-if="view.submit_action === 'REDIRECT'"
              class="choice-items__icon-active iconoir-check-circle"
            ></i
          ></a>
        </li>
      </ul>
    </FormGroup>

    <FormGroup
      v-if="view.submit_action === 'MESSAGE'"
      :label="$t('formViewMetaControls.theMessage')"
      small-label
      required
    >
      <FormTextarea
        v-model="submit_action_message"
        class="form-view__meta-message-textarea"
        :placeholder="$t('formViewMetaControls.theMessage')"
        :rows="3"
        :disabled="readOnly"
        @blur="
          $emit('updated-form', {
            submit_action_message,
          })
        "
      />
    </FormGroup>

    <FormGroup
      v-if="view.submit_action === 'REDIRECT'"
      small-label
      :error="$v.submit_action_redirect_url.$error"
      :error-message="redirectURLErrorMessage"
      :label="$t('formViewMetaControls.theURL')"
      :helper-text="$t('formViewMeta.includeRowId')"
      required
    >
      <FormInput
        v-model="submit_action_redirect_url"
        :placeholder="$t('formViewMetaControls.theURL')"
        :disabled="readOnly"
        :error="$v.submit_action_redirect_url.$error"
        @blur="
          ;[
            $v.submit_action_redirect_url.$touch(),
            !$v.submit_action_redirect_url.$error &&
              $emit('updated-form', {
                submit_action_redirect_url,
              }),
          ]
        "
      >
      </FormInput>
    </FormGroup>
  </div>
</template>

<script>
import { required, url, maxLength } from 'vuelidate/lib/validators'

// Must be kept in sync with
// `src/baserow/contrib/database/views/models.py::FormView::submit_action_redirect_url.max_length`
const redirectUrlMaxLength = 2000

export default {
  name: 'FormViewMetaControls',
  props: {
    view: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      submit_action_message: '',
      submit_action_redirect_url: '',
    }
  },
  computed: {
    redirectURLErrorMessage() {
      return this.$v.submit_action_redirect_url.$dirty &&
        !this.$v.submit_action_redirect_url.required
        ? this.$t('error.requiredField')
        : !this.$v.submit_action_redirect_url.url
        ? this.$t('error.invalidURL')
        : !this.$v.submit_action_redirect_url.maxLength
        ? this.$t('error.maxLength', { max: redirectUrlMaxLength })
        : ''
    },
  },
  watch: {
    'view.submit_action_message'(value) {
      this.submit_action_message = value
    },
    'view.submit_action_redirect_url'(value) {
      this.submit_action_redirect_url = value
    },
  },
  created() {
    this.submit_action_message = this.view.submit_action_message
    this.submit_action_redirect_url = this.view.submit_action_redirect_url
  },
  validations: {
    submit_action_redirect_url: {
      required,
      url,
      maxLength: maxLength(redirectUrlMaxLength),
    },
  },
}
</script>
