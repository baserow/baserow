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
          @blur="$v.values.title.$touch()"
        ></FormInput>
        <template #error>
          <span v-if="$v.values.title.$dirty && !$v.values.title.required">
            {{ $t('error.requiredField') }}
          </span>
          <span v-if="$v.values.title.$dirty && !$v.values.title.maxLength">
            {{ $t('error.maxLength', { max: 255 }) }}
          </span>
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
          @blur="$v.values.description.$touch()"
        ></FormTextarea>
        <template #error>
          <span
            v-if="
              $v.values.description.$dirty && !$v.values.description.maxLength
            "
          >
            {{ $t('error.maxLength', { max: 255 }) }}
          </span>
        </template>
      </FormGroup>
    </FormSection>
  </form>
</template>

<script>
import { required, maxLength } from 'vuelidate/lib/validators'
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
  data() {
    return {
      allowedValues: ['title', 'description'],
      values: {
        title: '',
        description: '',
      },
      emitValuesOnReset: false,
    }
  },
  validations() {
    return {
      values: {
        title: { required, maxLength: maxLength(255) },
        description: { maxLength: maxLength(255) },
      },
    }
  },
  watch: {
    widget: {
      handler(value) {
        this.reset(true)
      },
      deep: true,
    },
  },
}
</script>
