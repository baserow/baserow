<template>
  <div>
    <FormGroup
      small-label
      :label="$t('ratingElementForm.maxValue')"
      class="margin-bottom-2"
      required
    >
      <FormInput
        v-model="values.max_value"
        type="number"
        :min="0"
        :max="10"
        :to-value="(value) => parseInt(value) || 0"
      />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('ratingElementForm.color')"
      class="margin-bottom-2"
      required
    >
      <ColorInput v-model="values.color" />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('ratingElementForm.style')"
      class="margin-bottom-2"
      required
    >
      <Dropdown v-model="values.style">
        <DropdownItem :name="$t('ratingElementForm.star')" value="star" />
        <DropdownItem :name="$t('ratingElementForm.heart')" value="heart" />
        <DropdownItem
          :name="$t('ratingElementForm.thumbsUp')"
          value="thumbs-up"
        />
        <DropdownItem :name="$t('ratingElementForm.flag')" value="flag" />
      </Dropdown>
    </FormGroup>
  </div>
</template>

<script>
import FormGroup from '@baserow/modules/core/components/FormGroup.vue'
import ColorInput from '@baserow/modules/core/components/ColorInput.vue'
import Dropdown from '@baserow/modules/core/components/Dropdown.vue'
import DropdownItem from '@baserow/modules/core/components/DropdownItem.vue'

export default {
  name: 'RatingFormFields',
  components: {
    FormGroup,
    ColorInput,
    Dropdown,
    DropdownItem,
  },
  props: {
    values: {
      type: Object,
      required: true,
    },
  },
}
</script>
