<template>
  <FormGroup
    :label="$t('noteField.label')"
    :helper-text="$t('noteField.help')"
    :error="v$.note.$error"
    :error-message="v$.note.$errors[0]?.$message"
    small-label
  >
    <FormTextarea
      :value="values.note"
      :rows="rows"
      :placeholder="placeholder"
      :error="v$.note.$error"
      @input="onInput"
      @focus="focused = true"
      @blur="onBlur"
    />
  </FormGroup>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import useVuelidate from '@vuelidate/core'
import { helpers, maxLength as maxLengthValidator } from '@vuelidate/validators'

/**
 * The form field to edit the Markdown note of an object (see the backend
 * `NoteMixin`). Emits `input` with the new note, and only when it is valid, so
 * the parent can save whatever it receives.
 *
 * While the field has focus the text belongs to the person typing: a change of
 * `value` coming from the parent, such as the response of an earlier save, does
 * not replace it. The field follows `value` again once it loses focus. A parent
 * that reuses the field for another object must give it a `key`.
 */
const props = defineProps({
  value: {
    type: String,
    required: false,
    default: '',
  },
  placeholder: {
    type: String,
    required: false,
    default: null,
  },
  rows: {
    type: Number,
    required: false,
    default: 4,
  },
  // Mirrors `NOTE_MAX_LEN` in the backend.
  maxLength: {
    type: Number,
    required: false,
    default: 1000,
  },
})

const emit = defineEmits(['input'])

const { t } = useI18n()

const values = reactive({ note: props.value || '' })
const focused = ref(false)
watch(
  () => props.value,
  (value) => {
    if (!focused.value) {
      values.note = value || ''
    }
  }
)

const rules = computed(() => ({
  note: {
    maxLength: helpers.withMessage(
      t('error.maxLength', { max: props.maxLength }),
      maxLengthValidator(props.maxLength)
    ),
  },
}))
const v$ = useVuelidate(rules, values, { $lazy: true })

const onBlur = () => {
  focused.value = false
  // A rejected note stays visible with its error so it can be corrected.
  if (!v$.value.$invalid) {
    values.note = props.value || ''
  }
}

const onInput = (value) => {
  values.note = value
  v$.value.$touch()
  if (!v$.value.$invalid) {
    emit('input', value)
  }
}
</script>
