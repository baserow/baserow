<template>
  <div>
    <div
      ref="options"
      v-auto-overflow-scroll
      class="select-options select-options--scrollable"
    >
      <div
        v-for="(item, index) in options"
        :key="item.id"
        v-sortable="{
          id: item.id,
          update: order,
          handle: '[data-sortable-handle]',
          marginTop: -3,
        }"
        class="select-options__item"
      >
        <div class="select-options__drag-handle" data-sortable-handle></div>
        <a
          :ref="'color-select-' + index"
          :class="'select-options__color' + ' background-color--' + item.color"
          @click="openColor(index)"
        >
          <i class="iconoir-nav-arrow-down"></i>
        </a>
        <FormInput
          ref="inputs"
          v-model="item.value"
          :error="v$.options[index].$error"
          @input="$emit('input', value)"
          @blur="v$.options[index].$touch()"
        />
        <ButtonIcon
          tag="a"
          icon="iconoir-cancel"
          @click.stop.prevent="remove(index)"
        ></ButtonIcon>
      </div>
    </div>
    <ButtonText icon="iconoir-plus" tag="a" @click="add()">
      {{ $t('fieldSelectOptions.add') }}
    </ButtonText>
    <ColorSelectContext
      ref="colorContext"
      @selected="updateColor(colorContextSelected, $event)"
    ></ColorSelectContext>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'
import ColorSelectContext from '@baserow/modules/core/components/ColorSelectContext'
import { randomColor } from '@baserow/modules/core/utils/colors'

export default {
  name: 'FieldSelectOptions',
  components: { ColorSelectContext },
  props: {
    value: {
      type: Array,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      colorContextSelected: -1,
      lastSeenId: -1,
      options: [],
    }
  },
  computed: {
    usedColors() {
      const colors = new Set()
      this.options.forEach((option) => colors.add(option.color))
      return Array.from(colors)
    },
  },
  watch: {
    value: {
      immediate: true,
      handler(newVal) {
        this.options = newVal
      },
    },
  },
  methods: {
    remove(index) {
      this.$refs.colorContext.hide()
      this.options.splice(index, 1)
      this.$emit('input', this.options)
    },
    add(optionValue = '') {
      this.options.push({
        value: optionValue,
        color: randomColor(this.usedColors),
        id: this.lastSeenId,
      })
      this.$emit('input', this.options)
      this.lastSeenId -= 1
      this.$nextTick(() => {
        this.$refs.options.scrollTop = this.$refs.options.scrollHeight
        const lastIndex = this.$refs.inputs.length - 1
        const bottomInput = this.$refs.inputs[lastIndex]
        bottomInput.focus()
      })
    },
    openColor(index) {
      this.colorContextSelected = index
      this.$refs.colorContext.setActive(this.options[index].color)
      this.$refs.colorContext.toggle(
        this.$refs['color-select-' + index][0],
        'bottom',
        'left',
        4
      )
    },
    updateColor(index, color) {
      this.options[index].color = color
      this.$emit('input', this.value)
    },
    order(newOrder, oldOrder) {
      const sortedValue = this.options
        .slice()
        .sort(
          (a, b) =>
            newOrder.findIndex((id) => id === a.id) -
            newOrder.findIndex((id) => id === b.id)
        )
      this.$emit('input', sortedValue)
    },
  },
  validations() {
    const validations = { options: [] }
    this.options.forEach((option, index) => {
      validations.options[index] = {
        value: { required },
      }
    })
    return validations
  },
}
</script>
