<template>
  <Modal ref="modal" :small="true">
    <h2
      class="box__title automatic-snapshot-schedule__modal-title"
      :title="title"
    >
      {{ title }}
    </h2>
    <AutomaticSnapshotScheduleForm
      v-if="values"
      :key="formKey"
      ref="form"
      :default-values="values"
      :min-interval-minutes="minIntervalMinutes"
      @submitted="emit('submitted', $event)"
    >
      <div class="actions actions--right actions--gap">
        <Button type="secondary" size="large" @click="hide()">
          {{ $t('action.cancel') }}
        </Button>
        <Button
          size="large"
          :loading="saving"
          :disabled="saving"
          @click="form.submit()"
        >
          {{ $t('automaticSnapshots.save') }}
        </Button>
      </div>
    </AutomaticSnapshotScheduleForm>
  </Modal>
</template>

<script setup>
import { ref } from 'vue'
import AutomaticSnapshotScheduleForm from '@baserow_enterprise/components/automaticSnapshots/AutomaticSnapshotScheduleForm'

defineProps({
  title: {
    type: String,
    required: true,
  },
  minIntervalMinutes: {
    type: Number,
    required: true,
  },
  saving: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const emit = defineEmits(['submitted'])

const modal = ref(null)
const form = ref(null)
const values = ref(null)
// Changes every time the modal opens, so the form starts from `values` again.
const formKey = ref(0)

/**
 * Opens the modal with the form filled in with the provided schedule values.
 */
function show(scheduleValues) {
  values.value = scheduleValues
  formKey.value += 1
  modal.value.show()
}

function hide() {
  modal.value.hide()
}

defineExpose({ show, hide })
</script>
