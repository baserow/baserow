<template>
  <div class="control__elements">
    <ul class="field-multiple-select__items">
      <li
        v-for="item in value"
        :key="item.id"
        class="field-multiple-select__item"
        :class="'background-color--' + item.color"
      >
        <div class="field-multiple-select__name">
          {{ item.value }}
        </div>
        <a
          v-if="!readOnly"
          class="field-multiple-select__remove"
          @click.prevent="removeValue($event, value, item.id)"
        >
          <i class="iconoir-cancel"></i>
        </a>
      </li>
    </ul>
    <span v-if="!readOnly" ref="dropdownLink">
      <ButtonText icon="iconoir-plus" @click.prevent="toggleDropdown()">
        {{ $t('rowEditFieldMultipleSelect.addOption') }}
      </ButtonText></span
    >
    <FieldSelectOptionsDropdown
      ref="dropdown"
      :options="availableSelectOptions"
      :allow-create-option="allowCreateOptions"
      :disabled="readOnly"
      :show-input="false"
      :show-empty-value="false"
      :error="touched && !valid"
      @input="updateValue($event, value)"
      @create-option="createOption($event)"
      @hide="touch()"
    ></FieldSelectOptionsDropdown>
    <div v-show="touched && !valid" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import multipleSelectField from '@baserow/modules/database/mixins/multipleSelectField'
import FieldSelectOptionsDropdown from '@baserow/modules/database/components/field/FieldSelectOptionsDropdown'

export default {
  name: 'RowEditFieldMultipleSelect',
  components: { FieldSelectOptionsDropdown },
  mixins: [rowEditField, multipleSelectField],
  props: {
    allowCreateOptions: {
      type: Boolean,
      default: true,
      required: false,
    },
  },
}
</script>
