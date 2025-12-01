<template>
  <div class="baserow-table-wrapper">
    <table class="baserow-table" :class="`baserow-table--${orientation}`">
      <template v-if="orientation === ORIENTATIONS.HORIZONTAL">
        <thead>
          <tr class="baserow-table__row">
            <template v-for="field in fields">
              <slot name="field-name" :field="field">
                <th :key="field.__id__" class="baserow-table__header-cell">
                  {{ field.name }}
                </th>
              </slot>
            </template>
          </tr>
        </thead>
        <tbody v-if="rows.length">
          <tr
            v-for="(row, index) in rows"
            :key="row.__id__"
            class="baserow-table__row"
          >
            <template v-for="field in fields">
              <slot
                name="cell-content"
                :value="row[field.__id__]"
                :field="field"
                :row-index="index"
                :row="row"
              >
                <td :key="field.id" class="baserow-table__cell">
                  {{ row[field.__id__] }}
                </td>
              </slot>
            </template>
          </tr>
        </tbody>
      </template>
      <template v-else>
        <template v-if="rows.length">
          <tbody
            v-for="(row, rowIndex) in rows"
            :key="row.__id__"
            class="baserow-table__row"
          >
            <tr
              v-for="(field, fieldIndex) in fields"
              :key="`${row.__id__}_${field.__id__}`"
            >
              <slot name="field-name" :field="field">
                <th :key="field.__id__" class="baserow-table__header-cell">
                  {{ field.name }}
                </th>
              </slot>
              <slot
                name="cell-content"
                :value="row[field.__id__]"
                :field="field"
                :row-index="rowIndex"
                :row="row"
              >
                <td
                  class="baserow-table__cell"
                  :class="{
                    'baserow-table__separator':
                      fieldIndex === fields.length - 1,
                  }"
                >
                  {{ value }}
                </td>
              </slot>
            </tr>
          </tbody>
        </template>
      </template>
      <tbody v-if="!rows.length">
        <tr>
          <td class="baserow-table__empty-message" :colspan="fields.length">
            <slot name="empty-state"></slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
import { ORIENTATIONS } from '@baserow/modules/builder/enums'

export default {
  name: 'BaserowTable',
  inject: ['mode'],
  props: {
    fields: {
      type: Array,
      required: true,
    },
    rows: {
      type: Array,
      required: true,
    },
    orientation: {
      type: String,
      default: ORIENTATIONS.HORIZONTAL,
    },
  },
  computed: {
    ORIENTATIONS() {
      return ORIENTATIONS
    },
  },
}
</script>
