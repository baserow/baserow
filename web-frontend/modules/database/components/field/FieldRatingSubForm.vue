<template>
  <div class="rating-field-form">
    <FormGroup required small-label :label="$t('fieldRatingSubForm.color')">
      <a
        ref="color-select"
        :class="'rating-field__color' + ' background-color--' + values.color"
        @click="openColor()"
      >
        <i class="iconoir-nav-arrow-down"></i>
      </a>
    </FormGroup>

    <FormGroup
      required
      small-label
      :label="$t('fieldRatingSubForm.style')"
      :error="v$.style.$error"
    >
      <Dropdown
        v-model="v$.style.$model"
        class="dropdown--floating rating-field-form__dropdown-style"
        :error="v$.style.$error"
        :fixed-items="true"
        :show-search="false"
        @hide="v$.style.$touch"
      >
        <DropdownItem
          v-for="style in styles"
          :key="style"
          name=""
          :value="style"
          :icon="`baserow-icon-${style}`"
        />
      </Dropdown>
    </FormGroup>

    <FormGroup
      required
      small-label
      :label="$t('fieldRatingSubForm.maxValue')"
      :error="v$.max_value.$error"
    >
      <Dropdown
        v-model="v$.max_value.$model"
        class="dropdown--floating"
        :error="v$.max_value.$error"
        :show-search="false"
        :fixed-items="true"
        @hide="v$.max_value.$touch"
      >
        <DropdownItem
          v-for="index in 10"
          :key="index"
          :name="`${index}`"
          :value="index"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>

    <ColorSelectContext
      ref="colorContext"
      :colors="colors"
      @selected="updateColor($event)"
    ></ColorSelectContext>
  </div>
</template>

<script>
import { required } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'

import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import ColorSelectContext from '@baserow/modules/core/components/ColorSelectContext'

const colors = [['dark-blue', 'dark-green', 'dark-orange', 'dark-red']]

export default {
  name: 'FieldRatingSubForm',
  components: { ColorSelectContext },
  mixins: [form, fieldSubForm],
  data() {
    return {
      allowedValues: ['max_value', 'color', 'style'],
      values: null,
      v$: null,
      colors,
      styles: ['star', 'heart', 'thumbs-up', 'flag', 'smile'],
    }
  },
  created() {
    const values = reactive({
      max_value: 5,
      color: 'dark-orange',
      style: 'star',
    })

    const rules = computed(() => ({
      max_value: { required },
      color: { required },
      style: { required },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  methods: {
    openColor() {
      this.$refs.colorContext.setActive(this.values.color)
      this.$refs.colorContext.toggle(
        this.$refs['color-select'],
        'bottom',
        'left',
        4
      )
    },
    updateColor(color) {
      this.values.color = color
    },
  },
}
</script>
