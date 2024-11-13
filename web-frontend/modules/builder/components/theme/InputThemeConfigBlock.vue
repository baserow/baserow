<template>
  <div>
    <ThemeConfigBlockSection
      v-if="showLabel"
      :title="$t('inputThemeConfigBlock.label')"
    >
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.fontFamily')"
          class="margin-bottom-2"
        >
          <FontFamilySelector v-model="v$.label_font_family.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.label_font_family.$model"
              :default-value="theme?.label_font_family"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.textColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="v$.label_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.label_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.label_text_color.$model"
              :default-value="theme?.label_text_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.size')"
          :error-message="getError('label_font_size')"
          class="margin-bottom-2"
        >
          <PixelValueSelector v-model="v$.label_font_size.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.label_font_size.$model"
              :default-value="theme?.label_font_size"
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABFormGroup :label="$t('inputThemeConfigBlock.label')">
          <ABInput value="" />
        </ABFormGroup>
      </template>
    </ThemeConfigBlockSection>
    <ThemeConfigBlockSection :title="$t('inputThemeConfigBlock.input')">
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.fontFamily')"
          class="margin-bottom-2"
        >
          <FontFamilySelector v-model="v$.input_font_family.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.input_font_family.$model"
              :default-value="theme?.input_font_family"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.textColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="v$.input_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.input_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.input_text_color.$model"
              :default-value="theme?.input_text_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.size')"
          :error-message="getError('input_font_size')"
          class="margin-bottom-2"
        >
          <PixelValueSelector v-model="v$.input_font_size.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.input_font_size.$model"
              :default-value="theme?.input_font_size"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.backgroundColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="v$.input_background_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.input_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.input_background_color"
              :default-value="theme?.input_background_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.borderColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="v$.input_border_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.input_border_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.input_border_color.$model"
              :default-value="theme?.input_border_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.borderSize')"
          :error-message="getError('input_border_size')"
          class="margin-bottom-2"
        >
          <PixelValueSelector v-model="v$.input_border_size.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.input_border_size.$model"
              :default-value="theme?.input_border_size"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.borderRadius')"
          :error-message="getError('input_border_radius')"
          class="margin-bottom-2"
        >
          <PixelValueSelector v-model="v$.input_border_radius.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.input_border_radius.$model"
              :default-value="theme?.input_border_radius"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.padding')"
          :error-message="getInputPaddingError()"
          class="margin-bottom-2"
        >
          <PaddingSelector v-model="inputPadding" />
          <template #after-input>
            <ResetButton
              v-model="inputPadding"
              :default-value="
                theme
                  ? {
                      vertical: theme['input_vertical_padding'],
                      horizontal: theme['input_horizontal_padding'],
                    }
                  : undefined
              "
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABFormGroup>
          <ABInput
            :value="$t('inputThemeConfigBlock.input')"
            class="margin-bottom-2"
          />
          <ABDropdown
            :value="$t('inputThemeConfigBlock.input')"
            :show-search="false"
            class="margin-bottom-2"
          >
            <ABDropdownItem
              v-for="option in options"
              :key="option.value"
              :name="option.name"
              :value="option.value"
            />
          </ABDropdown>
          <div class="margin-bottom-2">
            <ABCheckbox
              v-for="(option, index) in options"
              :key="option.value"
              :name="option.name"
              :value="index === 1"
            >
              {{ option.name }}
            </ABCheckbox>
          </div>
          <div class="margin-bottom-2">
            <ABRadio
              v-for="(option, index) in options"
              :key="option.value"
              :value="index === 1"
            >
              {{ option.name }}
            </ABRadio>
          </div>
        </ABFormGroup>
      </template>
    </ThemeConfigBlockSection>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import FontFamilySelector from '@baserow/modules/builder/components/FontFamilySelector'
import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'
import PaddingSelector from '@baserow/modules/builder/components/PaddingSelector'
import { required, integer, minValue, maxValue } from '@vuelidate/validators'

const minMax = {
  label_font_size: {
    min: 1,
    max: 100,
  },
  input_font_size: {
    min: 1,
    max: 100,
  },
  input_border_size: {
    min: 0,
    max: 100,
  },
  input_border_radius: {
    min: 0,
    max: 100,
  },
  input_horizontal_padding: {
    min: 0,
    max: 200,
  },
  input_vertical_padding: {
    min: 0,
    max: 200,
  },
}

export default {
  name: 'LinkThemeConfigBlock',
  components: {
    ThemeConfigBlockSection,
    ResetButton,
    FontFamilySelector,
    PixelValueSelector,
    PaddingSelector,
  },
  mixins: [themeConfigBlock],
  data() {
    return {
      values: null,
      v$: null,
      options: [
        { name: 'Option 1', value: 1 },
        { name: 'Option 2', value: 2 },
        { name: 'Option 3', value: 3 },
      ],
    }
  },
  computed: {
    inputPadding: {
      get() {
        return {
          vertical: this.values.input_vertical_padding,
          horizontal: this.values.input_horizontal_padding,
        }
      },
      set(newValue) {
        this.v$.input_vertical_padding.$model = newValue.vertical
        this.v$.input_horizontal_padding.$model = newValue.horizontal
      },
    },
    showLabel() {
      return !this.extraArgs?.onlyInput
    },
  },
  created() {
    const values = reactive({
      ...Object.fromEntries(Object.entries(minMax).map(([key]) => [key, 1])),
      label_font_family: this.theme?.label_font_family,
      label_text_color: this.theme?.label_text_color,
      input_font_family: this.theme?.input_font_family,
      input_text_color: this.theme?.input_text_color,
      input_background_color: this.theme?.input_background_color,
      input_border_color: this.theme?.input_border_color,
      input_border_radius: this.theme?.input_border_radius,
    })

    const rules = computed(() => ({
      ...Object.fromEntries(
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
      label_font_family: {},
      label_text_color: {},
      input_font_family: {},
      input_text_color: {},
      input_background_color: {},
      input_border_color: {},
      input_border_radius: {},
    }))

    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  methods: {
    isAllowedKey(key) {
      return key.startsWith('input_') || key.startsWith('label_')
    },
    getError(property) {
      if (this.v$[property].$invalid) {
        return this.$t('error.minMaxValueField', minMax[property])
      }
      return null
    },
    getInputPaddingError() {
      return (
        this.getError('input_vertical_padding') ||
        this.getError('input_horizontal_padding')
      )
    },
  },
}
</script>
