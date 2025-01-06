<template>
  <form @submit.prevent>
    <FormGroup
      small-label
      :label="$t('generalForm.valueTitle')"
      class="margin-bottom-2"
      :required="true"
      :error-message="valueErrorMessage"
    >
      <InjectedFormulaInput
        v-model="values.value"
        :placeholder="$t('generalForm.valueRequiredPlaceholder')"
        @input="emitChange"
        @blur="$v.values.value.$touch()"
      />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('ratingElementForm.maxValue')"
      class="margin-bottom-2"
      required
    >
      <input
        type="number"
        v-model="values.max_value"
        :min="1"
        :max="10"
        :step="1"
        class="input input--large"
        @input="emitChange"
      />
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('ratingElementForm.color')"
      class="margin-bottom-2"
      required
    >
      <ColorInput v-model="values.color" @input="emitChange" />
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('ratingElementForm.style')"
      class="margin-bottom-2"
      required
    >
      <Dropdown v-model="values.style" @input="emitChange">
        <DropdownItem :name="$t('ratingElementForm.star')" value="star" />
        <DropdownItem :name="$t('ratingElementForm.heart')" value="heart" />
        <DropdownItem
          :name="$t('ratingElementForm.thumbsUp')"
          value="thumbs-up"
        />
        <DropdownItem :name="$t('ratingElementForm.flag')" value="flag" />
      </Dropdown>
    </FormGroup>
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import FormGroup from '@baserow/modules/core/components/FormGroup'
import ColorInput from '@baserow/modules/core/components/ColorInput'
import Dropdown from '@baserow/modules/core/components/Dropdown'
import DropdownItem from '@baserow/modules/core/components/DropdownItem'
import Checkbox from '@baserow/modules/core/components/Checkbox'

export default {
  name: 'RatingElementForm',
  components: {
    InjectedFormulaInput,
    FormGroup,
    ColorInput,
    Dropdown,
    DropdownItem,
    Checkbox,
  },
  mixins: [elementForm],
  validations: {
    values: {
      value: {
        required: true,
      },
    },
  },
  data() {
    return {
      values: {
        value: '',
        max_value: 5,
        color: '#fcbb03',
        style: 'star',
        required: false,
        label: '',
      },
    }
  },
  computed: {
    valueErrorMessage() {
      if (!this.$v.values.value.$error) {
        return ''
      }
      return this.$t('error.requiredField')
    },
  },
  watch: {
    element: {
      immediate: true,
      deep: true,
      handler(element) {
        if (element) {
          this.values = {
            value: element.value || '',
            max_value: element.max_value || 5,
            color: element.color || '#fcbb03',
            style: element.style || 'star',
            required: element.required || false,
            label: element.label || '',
          }
        }
      },
    },
  },
  methods: {
    emitChange() {
      this.$v.$touch()
      if (this.$v.$invalid) {
        return
      }
      this.$emit('values-changed', this.values)
    },
  },
}
</script>
