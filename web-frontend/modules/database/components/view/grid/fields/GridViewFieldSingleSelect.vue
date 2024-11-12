<template>
  <div ref="cell" class="grid-view__cell grid-field-single-select__cell active">
    <div
      ref="dropdownLink"
      class="grid-field-single-select grid-field-single-select--selected"
      :class="{ 'grid-field-single-select--read-only': readOnly }"
      @click="toggleDropdown()"
    >
      <div
        v-if="value !== null"
        class="grid-field-single-select__option"
        :class="'background-color--' + value.color"
      >
        {{ value.value }}
      </div>
      <i
        v-if="!readOnly"
        class="iconoir-nav-arrow-down grid-field-single-select__icon"
      ></i>
    </div>
    <slot name="default" :slot-props="{ editing, opened: true }"></slot>
    <FieldSelectOptionsDropdown
      v-if="!readOnly"
      ref="dropdown"
      :value="valueId"
      :options="field.select_options"
      :show-input="false"
      :allow-create-option="true"
      class="dropdown--floating"
      @show="editing = true"
      @hide="editing = false"
      @input="updateValue($event, value)"
      @create-option="createOption($event)"
    ></FieldSelectOptionsDropdown>
  </div>
</template>

<script>
import gridField from '@baserow/modules/database/mixins/gridField'
import singleSelectField from '@baserow/modules/database/mixins/singleSelectField'
import FieldSelectOptionsDropdown from '@baserow/modules/database/components/field/FieldSelectOptionsDropdown'

export default {
  components: { FieldSelectOptionsDropdown },
  mixins: [gridField, singleSelectField],
  data() {
    return {
      editing: false,
    }
  },
}
</script>
