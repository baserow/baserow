<template>
  <div>
    <div class="style-guide__wrapper">
      <div class="style-guide">
        <h2>Simple grid by default</h2>
        <div class="margin-bottom-5">
          <SimpleGrid :fields="fields" :rows="rows" />
        </div>
        <h2>Simple grid with all options</h2>
        <div
          class="margin-bottom-5"
          :style="{
            height: '400px',
            padding: '1em',
          }"
        >
          <SimpleGrid
            :fixed-fields="fixedFields"
            :fields="fields"
            :rows="rows"
            :full-height="true"
            :can-add-row="true"
            :with-footer="true"
            :show-hovered-row="true"
            :selected-rows="['2', '3']"
            :show-row-id="false"
            @add-row="onAddRow()"
            @row-click="onRowClick($event)"
          >
            <template #footLeft>
              <p>Made with love</p>
            </template>
          </SimpleGrid>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { useHead } from '#app'
import SimpleGrid from '@baserow/modules/database/components/view/grid/SimpleGrid'

export default {
  components: {
    SimpleGrid,
  },
  setup() {
    useHead({ title: 'Style guide' })
  },
  data() {
    return {
      fixedFields: [
        {
          id: 2744,
          table_id: 314,
          name: 'Name',
          order: 0,
          type: 'text',
          primary: true,
          text_default: '',
        },
        {
          id: 2747,
          table_id: 314,
          name: 'Date',
          order: 3,
          type: 'date',
          primary: false,
          date_format: 'EU',
          date_include_time: true,
          date_time_format: '24',
        },
      ],
      fields: [
        {
          id: 2753,
          table_id: 314,
          name: 'Select',
          order: 9,
          type: 'single_select',
          primary: false,
          select_options: [
            {
              id: 1419,
              value: 'Option 1',
              color: 'dark-red',
            },
            {
              id: 1420,
              value: 'Option 2',
              color: 'blue',
            },
            {
              id: 1421,
              value: 'option 3',
              color: 'light-blue',
            },
            {
              id: 1426,
              value: 'Option 4',
              color: 'light-green',
            },
          ],
        },
        {
          id: 2754,
          table_id: 314,
          name: 'Bool',
          order: 10,
          type: 'boolean',
          primary: false,
        },
        {
          id: 2755,
          table_id: 314,
          name: 'Multi',
          order: 11,
          type: 'multiple_select',
          primary: false,
          select_options: [
            {
              id: 1422,
              value: 'Option 1',
              color: 'dark-gray',
            },
            {
              id: 1423,
              value: 'Option 2',
              color: 'dark-orange',
            },
            {
              id: 1424,
              value: 'Option 3',
              color: 'light-green',
            },
            {
              id: 1425,
              value: 'Option 4',
              color: 'light-gray',
            },
            {
              id: 1427,
              value: 'Option 5',
              color: 'dark-blue',
            },
            {
              id: 1429,
              value: 'Option 6',
              color: 'dark-red',
            },
          ],
        },
        {
          id: 2756,
          table_id: 314,
          name: 'Number',
          order: 12,
          type: 'number',
          primary: false,
          number_decimal_places: 2,
          number_negative: true,
        },
        {
          id: 2758,
          table_id: 314,
          name: 'Star',
          order: 14,
          type: 'rating',
          primary: false,
          max_value: 5,
          color: 'dark-orange',
          style: 'star',
        },
        {
          id: 2760,
          table_id: 314,
          name: 'Number 2',
          order: 16,
          type: 'number',
          primary: false,
          number_decimal_places: 0,
          number_negative: false,
        },
        {
          id: 2761,
          table_id: 314,
          name: 'Multi2',
          order: 17,
          type: 'multiple_select',
          primary: false,
          select_options: [
            {
              id: 1416,
              value: 'A',
              color: 'blue',
            },
            {
              id: 1417,
              value: 'B',
              color: 'green',
            },
            {
              id: 1418,
              value: 'A',
              color: 'dark-red',
            },
          ],
        },
        {
          id: 2762,
          table_id: 314,
          name: 'File',
          order: 18,
          type: 'file',
          primary: false,
        },
      ],
      rows: [
        {
          field_2744: 'First',
          field_2753: {
            id: 1419,
            value: 'Option 1',
            color: 'dark-red',
          },
          field_2755: [
            {
              id: 1422,
              value: 'Option 2',
              color: 'dark-gray',
            },
            {
              id: 1427,
              value: 'Option 3',
              color: 'dark-blue',
            },
          ],
          field_2747: '2022-07-14T01:30:00Z',
          field_2754: true,
          field_2756: '10.00',
          field_2758: 3,
          field_2760: '2',
          field_2761: [
            {
              id: 1418,
              value: 'A',
              color: 'dark-red',
            },
            {
              id: 1417,
              value: 'B',
              color: 'green',
            },
          ],
          field_2762: [
            {
              name: 'KNAfSCPcJWzkLVDM5PpJMnYkJcy38C5y_4e743c0fcd7f6a06490f835504429b544470b28223d4d79246b11ade5d20bed4.webp',
              visible_name:
                '2019_09-20_FSNY_Gary_steer_DSC-...ary-scaled-e1596724598195.webp',
            },
          ],
          id: '1',
        },
        {
          field_2744: 'Second',
          field_2753: {
            id: 1420,
            value: 'Option 2',
            color: 'blue',
          },
          field_2755: [
            {
              id: 1422,
              value: 'Option 1,',
              color: 'dark-gray',
            },
            {
              id: 1427,
              value: 'Option 3',
              color: 'dark-blue',
            },
            {
              id: 1424,
              value: 'Option 1',
              color: 'light-green',
            },
          ],
          field_2747: '2022-01-11T12:00:00Z',
          field_2754: false,
          field_2756: '0.23',
          field_2758: 4,
          field_2760: '3',
          field_2761: [
            {
              id: 1418,
              value: 'A',
              color: 'dark-red',
            },
            {
              id: 1417,
              value: 'B',
              color: 'green',
            },
          ],
          field_2762: [
            {
              name: 'KZ5dwq9gGb53hnTRZuyvyqIwtShLw6OS_66364b0b0a9d66be651c675096eedc91cf05612d3180e91d05457491fa7df5f2.jpg',
              visible_name: 'atc-farmtour18-26_0.jpg',
            },
            {
              name: 't76OHsFw90XtykxLHauUjszZn9jxhemD_f21ee9a3fc93e1add245b0d3170589fd93b9a625f00e056a2f3c0070c36b11fa.webp',
              visible_name: 'Day_at_the_farm.webp',
            },
          ],
          id: '2',
        },
        {
          field_2744: 'Third',
          field_2753: {
            id: 1421,
            value: 'option 3',
            color: 'light-blue',
          },
          field_2755: [
            {
              id: 1424,
              value: 'Option 1',
              color: 'light-green',
            },
            {
              id: 1427,
              value: 'Option 3',
              color: 'dark-blue',
            },
          ],
          field_2747: '2022-01-11T12:00:00Z',
          field_2754: true,
          field_2756: null,
          field_2758: 4,
          field_2760: null,
          field_2761: [
            {
              id: 1418,
              value: 'A',
              color: 'dark-red',
            },
          ],
          field_2762: [
            {
              name: 'pDkRjvVAkKG8OqbCK84ScrPwDanX9cY0_017941b350850938479cd7613d00bdc46a29a579ed020e0731c3eb7595401517.jpg',
              visible_name: 'GMFD_FeaturePhoto.jpg',
            },
          ],
          id: '3',
        },
        {
          field_2744: 'Fourth',
          field_2753: {
            id: 1419,
            value: 'Option 1',
            color: 'dark-red',
          },
          field_2755: [
            {
              id: 1425,
              value: 'Option 4',
              color: 'light-gray',
            },
            {
              id: 1427,
              value: 'Option 3',
              color: 'dark-blue',
            },
          ],
          field_2747: '2022-07-14T01:30:00Z',
          field_2754: false,
          field_2756: '10.00',
          field_2758: 3,
          field_2760: '2',
          field_2761: [
            {
              id: 1418,
              value: 'A',
              color: 'dark-red',
            },
          ],
          field_2762: [
            {
              name: 'KNAfSCPcJWzkLVDM5PpJMnYkJcy38C5y_4e743c0fcd7f6a06490f835504429b544470b28223d4d79246b11ade5d20bed4.webp',
              visible_name: 'file.webp',
            },
          ],
          id: '4',
        },
      ],
    }
  },
  methods: {
    onAddRow() {
      this.rows.push({
        field_2744: '',
        field_2753: null,
        field_2755: [],
        field_2747: '',
        field_2754: false,
        field_2756: '',
        field_2758: 0,
        field_2760: '',
        field_2761: [],
        field_2762: [],
        id: '10',
      })
    },
    onRowClick(row) {
      alert(`Row ${row.id} has been clicked`)
    },
  },
}
</script>
