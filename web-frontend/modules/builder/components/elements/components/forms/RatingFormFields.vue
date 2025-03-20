<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('ratingElementForm.maxValue')"
      class="margin-bottom-2"
      :horizontal="horizontal"
      :error-message="getFirstErrorMessage('max_value')"
      required
    >
      <FormInput
        v-model="v$.values.max_value.$model"
        type="number"
        :min="1"
        :max="10"
        :to-value="(value) => parseInt(value) || 0"
      />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('ratingElementForm.color')"
      class="margin-bottom-2"
      :horizontal="horizontal"
      required
    >
      <ColorInput v-model="values.color" :color-variables="colorVariables" />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('ratingElementForm.ratingStyle')"
      class="margin-bottom-2"
      :horizontal="horizontal"
      required
    >
      <Dropdown v-model="values.rating_style">
        <DropdownItem
          v-for="style in ratingStyleChoices"
          :key="style.value"
          :name="style.name"
          :value="style.value"
        />
      </Dropdown>
    </FormGroup>
  </form>
</template>

<script>
import FormGroup from '@baserow/modules/core/components/FormGroup.vue'
import ColorInput from '@baserow/modules/core/components/ColorInput.vue'
import Dropdown from '@baserow/modules/core/components/Dropdown.vue'
import DropdownItem from '@baserow/modules/core/components/DropdownItem.vue'
import form from '@baserow/modules/core/mixins/form'
import { useVuelidate } from '@vuelidate/core'
import {
  required,
  integer,
  minValue,
  maxValue,
  helpers,
} from '@vuelidate/validators'
import { RATING_STYLES } from '@baserow/modules/core/enums'

export default {
  name: 'RatingFormFields',
  components: {
    FormGroup,
    ColorInput,
    Dropdown,
    DropdownItem,
  },
  mixins: [form],
  props: {
    horizontal: {
      type: Boolean,
      default: false,
    },
    colorVariables: {
      type: Array,
      default: () => [],
      required: false,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      values: { color: 'primary', max_value: 5, rating_style: 'star' },
      allowedValues: ['color', 'max_value', 'rating_style'],
    }
  },
  computed: {
    ratingStyleChoices() {
      return [
        {
          value: RATING_STYLES.STAR,
          name: this.$t('ratingElementForm.star'),
        },
        {
          value: RATING_STYLES.HEART,
          name: this.$t('ratingElementForm.heart'),
        },
        {
          value: RATING_STYLES.THUMBS_UP,
          name: this.$t('ratingElementForm.thumbsUp'),
        },
        {
          value: RATING_STYLES.FLAG,
          name: this.$t('ratingElementForm.flag'),
        },
        {
          value: RATING_STYLES.SMILE,
          name: this.$t('ratingElementForm.smile'),
        },
      ]
    },
  },
  validations() {
    return {
      values: {
        max_value: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: 1 }),
            minValue(1)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: 10 }),
            maxValue(10)
          ),
        },
      },
    }
  },
}
</script>
