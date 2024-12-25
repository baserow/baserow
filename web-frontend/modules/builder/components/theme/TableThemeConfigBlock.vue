<template>
  <div>
    <ThemeConfigBlockSection
      v-if="!onlyCell"
      :title="$t('tableThemeConfigBlock.table')"
    >
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('tableThemeConfigBlock.borderSize')"
          :error-message="getError('table_border_size')"
          class="margin-bottom-2"
        >
          <PixelValueSelector
            v-model="values.table_border_size"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`table_border_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="values.table_border_size"
              :default-value="theme?.table_border_size"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          required
          :label="$t('tableThemeConfigBlock.borderColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="values.table_border_color"
            :color-variables="colorVariables"
            :default-value="theme?.table_border_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.table_border_color"
              :default-value="theme?.table_border_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('tableThemeConfigBlock.borderRadius')"
          :error-message="getError('table_border_radius')"
          class="margin-bottom-2"
        >
          <PixelValueSelector
            v-model="values.table_border_radius"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`table_border_radius`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="values.table_border_radius"
              :default-value="theme?.table_border_radius"
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABTable :fields="fields" :rows="rows" />
      </template>
    </ThemeConfigBlockSection>

    <ThemeConfigBlockSection
      v-if="!onlyCell"
      :title="$t('tableThemeConfigBlock.header')"
    >
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('tableThemeConfigBlock.backgroundColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="values.table_header_background_color"
            :color-variables="colorVariables"
            :default-value="theme?.table_header_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.table_header_background_color"
              :default-value="theme?.table_header_background_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('tableThemeConfigBlock.fontFamily')"
          class="margin-bottom-2"
        >
          <FontFamilySelector v-model="values.table_header_font_family" />
          <template #after-input>
            <ResetButton
              v-model="values.table_header_font_family"
              :default-value="theme?.table_header_font_family"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('tableThemeConfigBlock.fontSize')"
          :error-message="getError('table_header_font_size')"
          class="margin-bottom-2"
        >
          <PixelValueSelector
            v-model="values.table_header_font_size"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`table_header_font_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="values.table_header_font_size"
              :default-value="theme?.table_header_font_size"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('tableThemeConfigBlock.textColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="values.table_header_text_color"
            :color-variables="colorVariables"
            :default-value="theme?.table_header_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.table_header_text_color"
              :default-value="theme?.table_header_text_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          required
          :label="$t('tableThemeConfigBlock.alignment')"
          class="margin-bottom-2"
        >
          <HorizontalAlignmentsSelector
            v-model="values.table_header_text_alignment"
          />

          <template #after-input>
            <ResetButton
              v-model="values.table_header_text_alignment"
              :default-value="theme?.table_header_text_alignment"
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABTable :fields="fields" :rows="rows" />
      </template>
    </ThemeConfigBlockSection>

    <ThemeConfigBlockSection :title="$t('tableThemeConfigBlock.cells')">
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('tableThemeConfigBlock.backgroundColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="values.table_cell_background_color"
            :color-variables="colorVariables"
            :default-value="theme?.table_cell_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.table_cell_background_color"
              :default-value="theme?.table_cell_background_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('tableThemeConfigBlock.backgroundAlternateColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="values.table_cell_alternate_background_color"
            :color-variables="colorVariables"
            :default-value="theme?.table_cell_alternate_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.table_cell_alternate_background_color"
              :default-value="theme?.table_cell_alternate_background_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          required
          :label="$t('tableThemeConfigBlock.alignment')"
          class="margin-bottom-2"
        >
          <HorizontalAlignmentsSelector v-model="values.table_cell_alignment" />
          <template #after-input>
            <ResetButton
              v-model="values.table_cell_alignment"
              :default-value="theme?.table_cell_alignment"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('tableThemeConfigBlock.padding')"
          :error-message="getPaddingError()"
          class="margin-bottom-2"
        >
          <PaddingSelector
            v-model="padding"
            :default-values-when-empty="paddingDefaults"
          />
          <template #after-input>
            <ResetButton
              v-model="padding"
              :default-value="
                theme
                  ? {
                      vertical: theme['table_cell_vertical_padding'],
                      horizontal: theme['table_cell_horizontal_padding'],
                    }
                  : undefined
              "
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABTable :fields="fields" :rows="rows" />
      </template>
    </ThemeConfigBlockSection>
    <ThemeConfigBlockSection
      v-if="!onlyCell"
      :title="$t('tableThemeConfigBlock.separators')"
    >
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('tableThemeConfigBlock.horizontalSeparatorColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="values.table_horizontal_separator_color"
            :color-variables="colorVariables"
            :default-value="theme?.table_horizontal_separator_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.table_horizontal_separator_color"
              :default-value="theme?.table_horizontal_separator_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('tableThemeConfigBlock.horizontalSeparatorSize')"
          :error-message="getError('table_horizontal_separator_size')"
          class="margin-bottom-2"
        >
          <PixelValueSelector
            v-model="values.table_horizontal_separator_size"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`table_horizontal_separator_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="values.table_horizontal_separator_size"
              :default-value="theme?.table_horizontal_separator_size"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('tableThemeConfigBlock.verticalSeparatorColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="values.table_vertical_separator_color"
            :color-variables="colorVariables"
            :default-value="theme?.table_vertical_separator_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.table_vertical_separator_color"
              :default-value="theme?.table_vertical_separator_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('tableThemeConfigBlock.verticalSeparatorSize')"
          :error-message="getError('table_vertical_separator_size')"
          class="margin-bottom-2"
        >
          <PixelValueSelector
            v-model="values.table_vertical_separator_size"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`table_vertical_separator_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="values.table_vertical_separator_size"
              :default-value="theme?.table_vertical_separator_size"
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABTable :fields="fields" :rows="rows" />
      </template>
    </ThemeConfigBlockSection>
  </div>
</template>

<script>
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'
import FontFamilySelector from '@baserow/modules/builder/components/FontFamilySelector'
import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'
import PaddingSelector from '@baserow/modules/builder/components/PaddingSelector'
import { required, integer, minValue, maxValue } from 'vuelidate/lib/validators'
import { DEFAULT_FONT_SIZE_PX } from '@baserow/modules/builder/defaultStyles'

const minMax = {
  table_border_size: {
    min: 0,
    max: 30,
  },
  table_border_radius: {
    min: 0,
    max: 100,
  },
  table_header_font_size: {
    min: 1,
    max: 100,
  },
  table_cell_vertical_padding: {
    min: 0,
    max: 100,
  },
  table_cell_horizontal_padding: {
    min: 0,
    max: 100,
  },
  table_horizontal_separator_size: {
    min: 0,
    max: 100,
  },
  table_vertical_separator_size: {
    min: 0,
    max: 100,
  },
}

export default {
  name: 'ButtonThemeConfigBlock',
  components: {
    ThemeConfigBlockSection,
    ResetButton,
    HorizontalAlignmentsSelector,
    FontFamilySelector,
    PixelValueSelector,
    PaddingSelector,
  },
  mixins: [themeConfigBlock],
  data() {
    return {
      values: {},
      fields: [
        { __id__: 1, id: 1, name: 'Header 1' },
        { __id__: 2, id: 2, name: 'Header 2' },
      ],
      rows: [
        { 'Header 1': 'Row 1 cell 1', 'Header 2': 'Row 1 cell 2' },
        { 'Header 1': 'Row 2 cell 1', 'Header 2': 'Row 2 cell 2' },
      ],
      defaultValuesWhenEmpty: {
        table_border_size: minMax.table_border_size.min,
        table_border_radius: minMax.table_border_radius.min,
        table_header_font_size: DEFAULT_FONT_SIZE_PX,
        table_horizontal_separator_size:
          minMax.table_horizontal_separator_size.min,
        table_vertical_separator_size: minMax.table_vertical_separator_size.min,
      },
    }
  },
  computed: {
    padding: {
      get() {
        return {
          vertical: this.values.table_cell_vertical_padding,
          horizontal: this.values.table_cell_horizontal_padding,
        }
      },
      set(newValue) {
        this.values.table_cell_vertical_padding = newValue.vertical
        this.values.table_cell_horizontal_padding = newValue.horizontal
      },
    },
    onlyCell() {
      return this.extraArgs?.onlyCell
    },
    paddingDefaults() {
      return {
        vertical: minMax.table_cell_vertical_padding.min,
        horizontal: minMax.table_cell_horizontal_padding.min,
      }
    },
  },
  methods: {
    isAllowedKey(key) {
      return key.startsWith('table_')
    },
    getError(property) {
      if (this.$v.values[property].$invalid) {
        return this.$t('error.minMaxValueField', minMax[property])
      }
      return null
    },
    getPaddingError() {
      return (
        this.getError('table_cell_vertical_padding') ||
        this.getError('table_cell_horizontal_padding')
      )
    },
  },
  validations: {
    values: Object.fromEntries(
      Object.entries(minMax).map(([key, limits]) => [
        key,
        {
          required,
          integer,
          minValue: minValue(limits.min),
          maxValue: maxValue(limits.max),
        },
      ])
    ),
  },
}
</script>
