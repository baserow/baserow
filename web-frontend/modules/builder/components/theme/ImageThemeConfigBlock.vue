<template>
  <div>
    <ThemeConfigBlockSection>
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          required
          :label="$t('imageThemeConfigBlock.alignment')"
          class="margin-bottom-2"
        >
          <HorizontalAlignmentsSelector
            v-model="v$.values.image_alignment.$model"
          />

          <template #after-input>
            <ResetButton
              v-model="v$.values.image_alignment.$model"
              :default-value="theme?.image_alignment"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          :label="$t('imageThemeConfigBlock.maxWidthLabel')"
          small-label
          required
          class="margin-bottom-2"
          :error="fieldHasErrors('image_max_width')"
        >
          <FormInput
            v-model="v$.values.image_max_width.$model"
            :error="fieldHasErrors('image_max_width')"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`image_min_width`]
            "
            type="number"
            :min="0"
            :max="100"
            remove-number-input-controls
            :placeholder="$t('imageThemeConfigBlock.maxWidthPlaceholder')"
            :to-value="(value) => (value ? parseInt(value) : null)"
          >
            <template #suffix>
              <i class="iconoir-percentage"></i>
            </template>
          </FormInput>

          <template #after-input>
            <ResetButton
              v-model="v$.values.image_max_width.$model"
              :default-value="theme?.image_max_width"
            />
          </template>
          <template #error>
            {{ v$.values.image_max_width.$errors[0].$message }}
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          required
          :label="$t('imageThemeConfigBlock.maxHeightLabel')"
          class="margin-bottom-2"
          :error="fieldHasErrors('image_max_height')"
        >
          <FormInput
            v-model="imageMaxHeight"
            type="number"
            remove-number-input-controls
            :error="fieldHasErrors('image_max_height')"
            :placeholder="$t('imageThemeConfigBlock.maxHeightPlaceholder')"
            :to-value="(value) => (value ? parseInt(value) : null)"
          >
            <template #suffix>px</template>
          </FormInput>

          <template #after-input>
            <ResetButton
              v-model="imageMaxHeight"
              :default-value="theme?.image_max_height"
            />
          </template>
          <template #error>
            {{ v$.values.image_max_height.$errors[0].$message }}
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('imageThemeConfigBlock.imageConstraintsLabel')"
        >
          <Dropdown
            v-model="v$.values.image_constraint.$model"
            fixed-items
            :show-search="true"
            class="flex-grow-1"
          >
            <DropdownItem
              v-for="{ name, label } in imageConstraintChoices"
              :key="name"
              :disabled="constraintDisabled(name)"
              :description="
                constraintDisabled(name)
                  ? $t(`imageThemeConfigBlock.imageConstraint${label}Disabled`)
                  : ''
              "
              :name="label"
              :value="name"
            >
            </DropdownItem>
          </Dropdown>
          <template #after-input>
            <ResetButton
              v-model="imageConstraintForReset"
              :default-value="theme?.image_constraint"
            />
          </template>
        </FormGroup>

        <FormGroup
          horizontal-narrow
          small-label
          required
          :label="$t('imageThemeConfigBlock.imageBorderRadiusType')"
          class="margin-bottom-2"
        >
          <BorderRadiusSelector v-model="values.image_border_radius_type" />

          <template #after-input>
            <ResetButton
              v-model="values.image_border_radius_type"
              :default-value="theme?.image_border_radius_type"
            />
          </template>
        </FormGroup>

        <FormGroup
          v-if="showBorderRadiusPercent"
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('imageThemeConfigBlock.imageBorderRadiusLabel')"
          :error="fieldHasErrors('image_border_radius_percent')"
        >
          <FormInput
            v-model="v$.values.image_border_radius_percent.$model"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`image_border_radius_percent`]
            "
            :error="fieldHasErrors('image_border_radius_percent')"
            type="number"
            :min="defaultValuesWhenEmpty.image_border_radius_percent.min"
            :max="defaultValuesWhenEmpty.image_border_radius_percent.max"
            remove-number-input-controls
            :placeholder="
              $t('imageThemeConfigBlock.imageBorderRadiusPercentPlaceholder')
            "
            :to-value="(value) => (value ? parseInt(value) : null)"
          >
            <template #suffix>
              <i class="iconoir-percentage"></i>
            </template>
          </FormInput>

          <template #after-input>
            <ResetButton
              v-model="values.image_border_radius_percent"
              :default-value="theme?.image_border_radius_percent"
            />
          </template>

          <template #error>
            {{ v$.values.image_border_radius_percent.$errors[0].$message }}
          </template>
        </FormGroup>

        <FormGroup
          v-if="showBorderRadiusPixel"
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('imageThemeConfigBlock.imageBorderRadiusLabel')"
          :error="fieldHasErrors('image_border_radius_pixel')"
        >
          <FormInput
            v-model="v$.values.image_border_radius_pixel.$model"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`image_border_radius_pixel`]
            "
            :error="fieldHasErrors('image_border_radius_pixel')"
            type="number"
            :min="defaultValuesWhenEmpty.image_border_radius_pixel.min"
            :max="defaultValuesWhenEmpty.image_border_radius_pixel.max"
            remove-number-input-controls
            :placeholder="
              $t('imageThemeConfigBlock.imageBorderRadiusPixelPlaceholder')
            "
            :to-value="(value) => (value ? parseInt(value) : null)"
          >
            <template #suffix>px</template>
          </FormInput>

          <template #after-input>
            <ResetButton
              v-model="values.image_border_radius_pixel"
              :default-value="theme?.image_border_radius_pixel"
            />
          </template>

          <template #error>
            {{ v$.values.image_border_radius_pixel.$errors[0].$message }}
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABImage src="/img/favicon_192.png" />
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
import BorderRadiusSelector from '@baserow/modules/builder/components/BorderRadiusSelector.vue'
import {
  IMAGE_SOURCE_TYPES,
  BORDER_RADIUS_TYPES,
} from '@baserow/modules/builder/enums'
import {
  integer,
  maxValue,
  minValue,
  required,
  helpers,
} from '@vuelidate/validators'

const minMax = {
  image_width: {
    min: 0,
    max: 100,
  },
  image_height: {
    min: 5,
    max: 3000,
  },
  image_border_radius_percent: {
    min: 0,
    max: 50,
  },
  image_border_radius_pixel: {
    min: 0,
    max: 100,
  },
}

export default {
  name: 'ImageThemeConfigBlock',
  components: {
    BorderRadiusSelector,
    ThemeConfigBlockSection,
    ResetButton,
    HorizontalAlignmentsSelector,
  },
  mixins: [themeConfigBlock],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        image_alignment: this.theme?.image_alignment,
        image_max_width: this.theme?.image_max_width,
        image_max_height: this.theme?.image_max_height,
        image_constraint: this.theme?.image_constraint,
        image_border_radius_type: this.theme?.image_border_radius_type,
        image_border_radius_pixel: this.theme?.image_border_radius_pixel,
        image_border_radius_percent: this.theme?.image_border_radius_percent,
      },
      allowedValues: [
        'image_alignment',
        'image_max_width',
        'image_max_height',
        'image_constraint',
        'image_border_radius_pixel',
        'image_border_radius_percent',
        'image_border_radius_type',
      ],
      defaultValuesWhenEmpty: {
        image_min_width: minMax.image_width.min,
        image_min_height: minMax.image_height.min,
        image_border_radius_pixel: minMax.image_border_radius_pixel.min,
        image_border_radius_percent: minMax.image_border_radius_percent.min,
      },
    }
  },
  computed: {
    borderRadiusTypes() {
      return [
        {
          label: this.$t('imageThemeConfigBlock.imageBorderRadiusTypePixel'),
          value: BORDER_RADIUS_TYPES.PIXEL,
        },
        {
          label: this.$t('imageThemeConfigBlock.imageBorderRadiusTypePercent'),
          value: BORDER_RADIUS_TYPES.PERCENT,
        },
      ]
    },
    showBorderRadiusPixel() {
      return this.values.image_border_radius_type === BORDER_RADIUS_TYPES.PIXEL
    },
    showBorderRadiusPercent() {
      return (
        this.values.image_border_radius_type === BORDER_RADIUS_TYPES.PERCENT
      )
    },
    imageMaxHeight: {
      get() {
        return this.values.image_max_height
      },
      set(newValue) {
        // If the `image_max_height` is emptied, and the
        // constraint is 'cover', then reset back to 'contain'.
        if (!newValue && this.v$.values.image_constraint.$model === 'cover') {
          this.v$.values.image_constraint.$model = 'contain'
        }
        // If the `image_max_height` is set, and the
        // constraint is 'contain', then reset back to 'cover'.
        if (newValue && this.v$.values.image_constraint.$model === 'contain') {
          this.v$.values.image_constraint.$model = 'cover'
        }
        this.v$.values.image_max_height.$model = newValue
      },
    },
    imageMaxHeightForReset: {
      get() {
        return { image_max_height: this.imageMaxHeight }
      },
      set(value) {
        this.imageMaxHeight = value.imageMaxHeight
      },
    },
    imageConstraintForReset: {
      get() {
        return this.values.image_constraint
      },
      set(value) {
        if (value === 'contain') {
          // Reset the height as we can't have a max height with contain
          this.v$.values.image_max_height.$model = null
        }
        if (value === 'cover') {
          // Set the height to what is defined in theme
          this.v$.values.image_max_height.$model = this.theme.image_max_height
        }
        this.v$.values.image_constraint.$model = value
      },
    },
    IMAGE_SOURCE_TYPES() {
      return IMAGE_SOURCE_TYPES
    },
    imageConstraintChoices() {
      return [
        {
          name: 'contain',
          label: this.$t('imageThemeConfigBlock.imageConstraintContain'),
        },
        {
          name: 'cover',
          label: this.$t('imageThemeConfigBlock.imageConstraintCover'),
        },
        {
          name: 'full-width',
          label: this.$t('imageThemeConfigBlock.imageConstraintFullWidth'),
        },
      ]
    },
  },
  methods: {
    constraintDisabled(name) {
      if (name === 'cover') {
        return !this.v$.values.image_max_height.$model
      } else if (name === 'contain') {
        return !!(
          this.v$.values.image_max_height.$model &&
          this.v$.values.image_max_height.$model > 0
        )
      }
    },
    isAllowedKey(key) {
      return key.startsWith('image_')
    },
  },
  validations() {
    return {
      values: {
        image_max_width: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: minMax.image_width.min }),
            minValue(minMax.image_width.min)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: minMax.image_width.max }),
            maxValue(minMax.image_width.max)
          ),
        },
        image_max_height: {
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: minMax.image_height.min }),
            minValue(minMax.image_height.min)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: minMax.image_height.max }),
            maxValue(minMax.image_height.max)
          ),
        },
        image_constraint: {},
        image_alignment: {},
        image_border_radius_percent: {
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', {
              min: minMax.image_border_radius_percent.min,
            }),
            minValue(minMax.image_border_radius_percent.min)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', {
              max: minMax.image_border_radius_percent.max,
            }),
            maxValue(minMax.image_border_radius_percent.max)
          ),
        },
        image_border_radius_pixel: {
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', {
              min: minMax.image_border_radius_pixel.min,
            }),
            minValue(minMax.image_border_radius_pixel.min)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', {
              max: minMax.image_border_radius_pixel.max,
            }),
            maxValue(minMax.image_border_radius_pixel.max)
          ),
        },
      },
    }
  },
}
</script>
