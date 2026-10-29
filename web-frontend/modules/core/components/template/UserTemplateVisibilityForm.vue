<template>
  <FormGroup
    :label="$t('userTemplateVisibilityForm.visibility')"
    small-label
    required
    :helper-text="
      modelValue.makePublic
        ? $t('userTemplateVisibilityForm.publicDescription')
        : $t('userTemplateVisibilityForm.privateDescription')
    "
  >
    <SegmentControl
      :segments="segments"
      size="small"
      :active-index="modelValue.makePublic ? 1 : 0"
      @update:active-index="choose($event === 1)"
    />
    <div v-if="modelValue.makePublic" class="user-template-form__consent">
      <Checkbox
        :model-value="modelValue.publicListingConsent"
        @update:model-value="
          emit('update:modelValue', {
            ...modelValue,
            publicListingConsent: $event,
          })
        "
      >
        <i18n-t keypath="userTemplateVisibilityForm.consent" tag="span">
          <template #author>
            <strong>{{ $store.getters['auth/getName'] }}</strong>
          </template>
        </i18n-t>
      </Checkbox>
    </div>
  </FormGroup>
</template>

<script setup>
import { computed } from 'vue'
import { useNuxtApp } from '#app'

const props = defineProps({
  // The visibility: `{ makePublic, publicListingConsent }`. Public is only valid
  // once the author agreed to be listed.
  modelValue: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['update:modelValue'])

const { $i18n } = useNuxtApp()

const segments = computed(() => [
  { label: $i18n.t('userTemplateVisibilityForm.private') },
  { label: $i18n.t('userTemplateVisibilityForm.public') },
])

function choose(makePublic) {
  if (makePublic === props.modelValue.makePublic) {
    return
  }
  // Agreed again each time Public is chosen.
  emit('update:modelValue', { makePublic, publicListingConsent: false })
}
</script>
