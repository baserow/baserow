<template>
  <div class="form-view__meta-controls">
    <SwitchInput
      v-if="
        $hasPermission(
          'database.table.view.can_receive_notification_on_submit_form_view',
          view,
          database.workspace.id
        )
      "
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
      <SegmentControl
        v-if="!readOnly"
        :active-index="
          submitActions.findIndex((s) => s.type === view.submit_action)
        "
        :segments="submitActions"
        @update:activeIndex="
          $emit('updated-form', { submit_action: submitActions[$event].type })
        "
      ></SegmentControl>
    </FormGroup>

    <FormGroup
      v-if="view.submit_action === 'MESSAGE'"
      :label="$t('formViewMetaControls.theMessage')"
      small-label
      required
    >
      <FormTextarea
        v-model="values.submit_action_message"
        class="form-view__meta-message-textarea"
        :placeholder="$t('formViewMetaControls.theMessage')"
        :rows="3"
        :disabled="readOnly"
        @blur="
          $emit('updated-form', {
            submit_action_message: values.submit_action_message,
          })
        "
      />
    </FormGroup>

    <FormGroup
      v-if="view.submit_action === 'REDIRECT'"
      small-label
      :error="v$.values.submit_action_redirect_url.$error"
      :label="$t('formViewMetaControls.theURL')"
      :helper-text="$t('formViewMeta.includeRowId')"
      required
    >
      <FormInput
        v-model="v$.values.submit_action_redirect_url.$model"
        :placeholder="$t('formViewMetaControls.theURL')"
        :disabled="readOnly"
        :error="v$.values.submit_action_redirect_url.$error"
        @blur="
          ;[
            !v$.values.submit_action_redirect_url.$error &&
              $emit('updated-form', {
                submit_action_redirect_url:
                  v$.values.submit_action_redirect_url.$model,
              }),
          ]
        "
      >
      </FormInput>

      <template #error>
        {{ v$.values.submit_action_redirect_url.$errors[0]?.$message }}
      </template>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, url, maxLength, helpers } from '@vuelidate/validators'
import { reactive, getCurrentInstance } from 'vue'

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
  setup() {
    const instance = getCurrentInstance()

    const values = reactive({
      values: {
        submit_action_message: '',
        submit_action_redirect_url: '',
      },
    })

    const rules = {
      values: {
        submit_action_redirect_url: {
          required: helpers.withMessage(
            instance.proxy.$t('error.requiredField'),
            required
          ),
          url: helpers.withMessage(instance.proxy.$t('error.invalidURL'), url),
          maxLength: helpers.withMessage(
            instance.proxy.$t('error.maxLength', { max: redirectUrlMaxLength }),
            maxLength(redirectUrlMaxLength)
          ),
        },
      },
    }

    return {
      values: values.values,
      v$: useVuelidate(rules, values, { $lazy: true }),
    }
  },
  data() {
    return {
      submitActions: [
        {
          type: 'MESSAGE',
          label: this.$t('formViewMetaControls.showMessage'),
        },
        {
          type: 'REDIRECT',
          label: this.$t('formViewMetaControls.urlRedirect'),
        },
      ],
    }
  },
  watch: {
    'view.submit_action_message'(value) {
      this.values.submit_action_message = value
    },
    'view.submit_action_redirect_url'(value) {
      this.values.submit_action_redirect_url = value
    },
  },
  created() {
    this.values.submit_action_message = this.view.submit_action_message
    this.values.submit_action_redirect_url =
      this.view.submit_action_redirect_url
  },
}
</script>
