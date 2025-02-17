<template>
  <form class="context__form" @submit.prevent="submit">
    <FormGroup
      :label="$t('kanbanViewOptionForm.selectOption')"
      required
      :error="fieldHasErrors('value')"
      class="margin-bottom-2"
    >
      <div class="kanban-view__option-item">
        <div class="select-options">
          <div class="select-options__item">
            <a
              ref="colorSelect"
              :class="
                'select-options__color' + ' background-color--' + values.color
              "
              @click="
                $refs.colorContext.toggle(
                  $refs.colorSelect,
                  'bottom',
                  'left',
                  4
                )
              "
            >
              <i class="iconoir-nav-arrow-down"></i>
            </a>
          </div>
        </div>
        <FormInput
          v-model="values.value"
          :error="fieldHasErrors('value')"
          @blur="v$.values.value.$touch"
        >
        </FormInput>
      </div>
      <template #error> {{ $t('error.requiredField') }}</template>
    </FormGroup>

    <slot></slot>
    <ColorSelectContext
      ref="colorContext"
      @selected="values.color = $event"
    ></ColorSelectContext>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import { randomColor } from '@baserow/modules/core/utils/colors'
import ColorSelectContext from '@baserow/modules/core/components/ColorSelectContext'

export default {
  name: 'KanbanViewOptionForm',
  components: { ColorSelectContext },
  mixins: [form],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['color', 'value'],
      values: {
        color: randomColor(),
        value: '',
      },
    }
  },
  validations() {
    return {
      values: {
        value: { required },
      },
    }
  },
}
</script>
