<template>
  <form @submit.prevent>
    <div class="control">
      <label class="control__label">{{ $t('ratingFieldForm.maxValue') }}</label>
      <div class="control__elements">
        <input
          type="number"
          :value="Number(values.max_value)"
          :min="1"
          :max="10"
          :step="1"
          class="input input--large"
          @input="$emit('input', values)"
        />
      </div>
    </div>
    <div class="control">
      <label class="control__label">{{ $t('ratingFieldForm.value') }}</label>
      <div class="control__elements">
        <InjectedFormulaInput
          v-model="values.value"
          @input="$emit('input', values)"
        />
      </div>
    </div>
    <div class="control">
      <label class="control__label">{{ $t('ratingFieldForm.color') }}</label>
      <div class="control__elements">
        <ColorInput v-model="values.color" @input="$emit('input', values)" />
      </div>
    </div>
    <div class="control">
      <label class="control__label">{{ $t('ratingFieldForm.style') }}</label>
      <div class="control__elements">
        <Dropdown v-model="values.style" @input="$emit('input', values)">
          <DropdownItem :name="$t('ratingFieldForm.star')" value="star" />
          <DropdownItem :name="$t('ratingFieldForm.heart')" value="heart" />
          <DropdownItem
            :name="$t('ratingFieldForm.thumbsUp')"
            value="thumbs-up"
          />
          <DropdownItem :name="$t('ratingFieldForm.flag')" value="flag" />
        </Dropdown>
      </div>
    </div>
  </form>
</template>

<script>
import collectionFieldForm from '@baserow/modules/builder/mixins/collectionFieldForm'
import ColorInput from '@baserow/modules/core/components/ColorInput'
import Dropdown from '@baserow/modules/core/components/Dropdown'
import DropdownItem from '@baserow/modules/core/components/DropdownItem'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'RatingFieldForm',
  components: {
    ColorInput,
    Dropdown,
    DropdownItem,
    InjectedFormulaInput,
  },
  mixins: [collectionFieldForm],
  data() {
    return {
      allowedValues: ['max_value', 'color', 'style', 'value'],
      values: {
        max_value: 5,
        color: '#fcbb03',
        style: 'star',
        value: '',
      },
    }
  },
}
</script>
