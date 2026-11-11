<template>
  <div>
    <FormGroup
      :label="$t('userTemplateDetailsForm.name')"
      small-label
      required
      :error-message="nameError"
      class="margin-bottom-2"
    >
      <div class="user-template-form__name">
        <button
          ref="iconButton"
          type="button"
          class="user-template-form__icon-button"
          :title="$t('userTemplateDetailsForm.chooseIcon')"
          :disabled="disabled"
          @click="iconContext.toggle(iconButton, 'bottom', 'left', 4)"
        >
          <i :class="modelValue.icon"></i>
          <i
            class="user-template-form__icon-button-arrow iconoir-nav-arrow-down"
          ></i>
        </button>
        <FormInput
          :model-value="modelValue.name"
          class="user-template-form__name-input"
          :maxlength="NAME_MAX_LENGTH"
          :placeholder="$t('userTemplateDetailsForm.namePlaceholder')"
          :error="Boolean(nameError)"
          :disabled="disabled"
          @update:model-value="update({ name: $event })"
        />
      </div>
      <TemplateIconSelectContext
        ref="iconContext"
        :active="modelValue.icon"
        @selected="update({ icon: $event })"
      />
    </FormGroup>

    <FormGroup
      :label="$t('userTemplateDetailsForm.description')"
      small-label
      :helper-text="`${modelValue.description.length} / ${DESCRIPTION_MAX_LENGTH}`"
      class="margin-bottom-2"
    >
      <FormTextarea
        :model-value="modelValue.description"
        :rows="2"
        :maxlength="DESCRIPTION_MAX_LENGTH"
        :placeholder="$t('userTemplateDetailsForm.descriptionPlaceholder')"
        :disabled="disabled"
        @update:model-value="update({ description: $event })"
      />
    </FormGroup>

    <FormGroup
      v-if="categories.length > 0"
      :label="$t('userTemplateDetailsForm.categories')"
      small-label
      required
      :error-message="categoriesError"
    >
      <div class="user-template-form__categories">
        <Chips
          v-for="category in categories"
          :key="category.id"
          type="button"
          size="small"
          :active="modelValue.categoryIds.includes(category.id)"
          :disabled="disabled"
          @click="toggleCategory(category.id)"
        >
          {{ category.name }}
        </Chips>
      </div>
    </FormGroup>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useNuxtApp } from '#app'

import TemplateIconSelectContext from '@baserow/modules/core/components/template/TemplateIconSelectContext'

// Mirrors the limits of the job request.
const NAME_MAX_LENGTH = 64
const DESCRIPTION_MAX_LENGTH = 80

const props = defineProps({
  // The details: `{ name, description, icon, categoryIds }`.
  modelValue: {
    type: Object,
    required: true,
  },
  // The categories an author can pick from, each with an `id` and a `name`. An
  // instance that never synced the templates has none, and then none is needed.
  categories: {
    type: Array,
    required: true,
  },
  // Whether the errors are shown, which is after the first attempt to submit.
  showErrors: {
    type: Boolean,
    required: false,
    default: false,
  },
  disabled: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue'])

const { $i18n } = useNuxtApp()

const iconButton = ref(null)
const iconContext = ref(null)

function isNameValid() {
  return props.modelValue.name.trim() !== ''
}

function isCategoriesValid() {
  return (
    props.categories.length === 0 || props.modelValue.categoryIds.length > 0
  )
}

const nameError = computed(() =>
  props.showErrors && !isNameValid()
    ? $i18n.t('userTemplateDetailsForm.nameRequired')
    : ''
)

const categoriesError = computed(() =>
  props.showErrors && !isCategoriesValid()
    ? $i18n.t('userTemplateDetailsForm.categoriesRequired')
    : ''
)

function update(values) {
  emit('update:modelValue', { ...props.modelValue, ...values })
}

function toggleCategory(categoryId) {
  if (props.disabled) {
    return
  }
  const categoryIds = props.modelValue.categoryIds
  update({
    categoryIds: categoryIds.includes(categoryId)
      ? categoryIds.filter((id) => id !== categoryId)
      : [...categoryIds, categoryId],
  })
}

/**
 * Whether the details can be submitted.
 */
function isValid() {
  return isNameValid() && isCategoriesValid()
}

defineExpose({ isValid })
</script>
