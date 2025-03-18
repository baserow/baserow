<template>
  <form
    class="widget-settings-base-form"
    @submit.prevent
    @keydown.enter.prevent
  >
    <FormSection>
      <FormGroup
        small-label
        :label="$t('widgetSettings.title')"
        :error="fieldHasErrors('title')"
        class="margin-bottom-2"
        required
      >
        <FormInput
          ref="title"
          v-model="values.title"
          :placeholder="$t('widgetSettings.title')"
          :error="fieldHasErrors('title')"
          @input="v$.values.title.$touch"
        ></FormInput>
        <template #error>
          {{ v$.values.title.$errors[0].$message }}
        </template>
      </FormGroup>
      <FormGroup
        small-label
        :label="$t('widgetSettings.description')"
        :error="fieldHasErrors('description')"
        class="margin-bottom-2"
      >
        <FormTextarea
          ref="description"
          v-model="values.description"
          :max-rows="2"
          :auto-expandable="true"
          size="small"
          :placeholder="$t('widgetSettings.description') + '...'"
          :error="fieldHasErrors('description')"
          @input="v$.values.description.$touch"
        ></FormTextarea>
        <template #error>
          {{ v$.values.description.$errors[0].$message }}
        </template>
      </FormGroup>
    </FormSection>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, maxLength, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'WidgetSettingsBaseForm',
  mixins: [form],
  props: {
    widget: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['title', 'description'],
      values: {
        title: '',
        description: '',
      },
      skipFirstValuesEmit: true,
    }
  },
  validations() {
    return {
      values: {
        title: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: 255 }),
            maxLength(255)
          ),
        },
        description: {
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: 255 }),
            maxLength(255)
          ),
        },
      },
    }
  },
  watch: {
    widget: {
      async handler(value) {
        this.setEmitValues(false)
        // Reset the form to set default values
        // again after a different widget is selected
        await this.reset(true)
        // Run form validation so that
        // problems are highlighted immediately
        this.v$.$touch()
        await this.$nextTick()
        this.setEmitValues(true)
      },
      deep: true,
    },
  },
}
</script>
