<template>
  <div ref="cell" class="grid-view__cell grid-field-many-to-many__cell active">
    <div
      ref="dropdownLink"
      class="grid-field-many-to-many__list grid-field-multiple-select__list"
    >
      <div
        v-for="item in value"
        :key="item.id"
        class="grid-field-multiple-select__item"
        :class="'background-color--' + item.color"
      >
        <div class="grid-field-many-to-many__name">
          {{ item.value }}
        </div>
        <a
          v-if="!readOnly"
          class="grid-field-many-to-many__remove"
          @click.prevent="removeValue($event, value, item.id)"
        >
          <i class="iconoir-cancel"></i>
        </a>
      </div>
      <a
        v-if="!readOnly"
        class="grid-field-many-to-many__item grid-field-many-to-many__item--link"
        @click.prevent="toggleDropdown()"
      >
        <i class="iconoir-plus"></i>
      </a>
    </div>
    <FieldSelectOptionsDropdown
      v-if="!readOnly"
      ref="dropdown"
      :options="availableSelectOptions"
      :show-input="false"
      :show-empty-value="false"
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
import multipleSelectField from '@baserow/modules/database/mixins/multipleSelectField'
import FieldSelectOptionsDropdown from '@baserow/modules/database/components/field/FieldSelectOptionsDropdown'

export default {
  components: { FieldSelectOptionsDropdown },
  mixins: [gridField, multipleSelectField],
  emits: ['editing-changed'],
  data() {
    return {
      editing: false,
    }
  },
  watch: {
    editing(editing) {
      this.$emit('editing-changed', editing)
    },
  },
}
</script>
