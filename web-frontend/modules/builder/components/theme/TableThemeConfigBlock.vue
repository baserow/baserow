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
            v-model="v$.values.table_border_size.$model"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`table_border_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.table_border_size.$model"
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
            v-model="v$.values.table_border_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.table_border_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.table_border_color.$model"
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
            v-model="v$.values.table_border_radius.$model"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`table_border_radius`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.table_border_radius.$model"
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
            v-model="v$.values.table_header_background_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.table_header_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.table_header_background_color.$model"
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
          <FontFamilySelector
            v-model="v$.values.table_header_font_family.$model"
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.table_header_font_family.$model"
              :default-value="theme?.table_header_font_family"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('tableThemeConfigBlock.fontWeight')"
        >
          <FontWeightSelector
            v-model="values.table_header_font_weight"
            :font="values.table_header_font_family"
          />
          <template #after-input>
            <ResetButton
              v-if="
                values.table_header_font_family ===
                theme?.table_header_font_family
              "
              v-model="values.table_header_font_weight"
              :default-value="theme?.table_header_font_weight"
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
            v-model="v$.values.table_header_font_size.$model"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`table_header_font_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.table_header_font_size.$model"
              :default-value="theme?.table_header_font_size"
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
            v-model="v$.values.table_header_text_alignment.$model"
          />

          <template #after-input>
            <ResetButton
              v-model="v$.values.table_header_text_alignment.$model"
              :default-value="theme?.table_header_text_alignment"
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
            v-model="v$.values.table_header_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.table_header_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.table_header_text_color.$model"
              :default-value="theme?.table_header_text_color"
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
            v-model="v$.values.table_cell_background_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.table_cell_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.table_cell_background_color.$model"
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
            v-model="v$.values.table_cell_alternate_background_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.table_cell_alternate_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.table_cell_alternate_background_color.$model"
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
          <HorizontalAlignmentsSelector
            v-model="v$.values.table_cell_alignment.$model"
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.table_cell_alignment.$model"
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
            v-model="v$.values.table_horizontal_separator_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.table_horizontal_separator_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.table_horizontal_separator_color.$model"
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
            v-model="v$.values.table_horizontal_separator_size.$model"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`table_horizontal_separator_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.table_horizontal_separator_size.$model"
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
            v-model="v$.values.table_vertical_separator_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.table_vertical_separator_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.table_vertical_separator_color.$model"
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
            v-model="v$.values.table_vertical_separator_size.$model"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`table_vertical_separator_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.table_vertical_separator_size.$model"
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
import { useVuelidate } from '@vuelidate/core'
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'
import FontFamilySelector from '@baserow/modules/builder/components/FontFamilySelector'
import FontWeightSelector from '@baserow/modules/builder/components/FontWeightSelector'
import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'
import PaddingSelector from '@baserow/modules/builder/components/PaddingSelector'
import { DEFAULT_FONT_SIZE_PX } from '@baserow/modules/builder/defaultStyles'
import {
  required,
  integer,
  minValue,
  maxValue,
  helpers,
} from '@vuelidate/validators'

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
    FontWeightSelector,
    PixelValueSelector,
    PaddingSelector,
  },
  mixins: [themeConfigBlock],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      values: {
        ...Object.fromEntries(Object.entries(minMax).map(([key]) => [key, 1])),
        table_border_color: this.theme?.table_border_color,
        table_header_background_color:
          this.theme?.table_header_background_color,
        table_header_font_family: this.theme?.table_header_font_family,
        table_header_text_color: this.theme?.table_header_text_color,
        table_header_text_alignment: this.theme?.table_header_text_alignment,
        table_cell_background_color: this.theme?.table_cell_background_color,
        table_cell_alternate_background_color:
          this.theme?.table_cell_alternate_background_color,
        table_cell_alignment: this.theme?.table_cell_alignment,
        table_horizontal_separator_color:
          this.theme?.table_horizontal_separator_color,
        table_vertical_separator_color:
          this.theme?.table_vertical_separator_color,
      },
      fields: [
        { __id__: 1, id: 1, name: 'Header 1' },
        { __id__: 2, id: 2, name: 'Header 2' },
      ],
      rows: [
        {
          1: 'Row 1 cell 1',
          2: 'Row 1 cell 2',
          __id__: 0,
        },
        {
          1: 'Row 2 cell 1',
          2: 'Row 2 cell 2',
          __id__: 1,
        },
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
        this.v$.values.table_cell_vertical_padding.$model = newValue.vertical
        this.v$.values.table_cell_horizontal_padding.$model =
          newValue.horizontal
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
      return this.v$.values[property].$errors[0]?.$message
    },
    getPaddingError() {
      return (
        this.getError('table_cell_vertical_padding') ||
        this.getError('table_cell_horizontal_padding')
      )
    },
  },
  validations() {
    return {
      values: {
        ...Object.fromEntries(
          Object.entries(minMax).map(([key, limits]) => [
            key,
            {
              required: helpers.withMessage(
                this.$t('error.requiredField'),
                required
              ),
              integer: helpers.withMessage(
                this.$t('error.integerField'),
                integer
              ),
              minValue: helpers.withMessage(
                this.$t('error.minValueField', {
                  min: limits.min,
                }),
                minValue(limits.min)
              ),
              maxValue: helpers.withMessage(
                this.$t('error.maxValueField', {
                  max: limits.max,
                }),
                maxValue(limits.max)
              ),
            },
          ])
        ),
        table_border_color: {},
        table_header_background_color: {},
        table_header_font_family: {},
        table_header_text_color: {},
        table_header_text_alignment: {},
        table_cell_background_color: {},
        table_cell_alternate_background_color: {},
        table_cell_alignment: {},
        table_horizontal_separator_color: {},
        table_vertical_separator_color: {},
      },
    }
  },
}
</script>
