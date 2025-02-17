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
          class="margin-bottom-2"
          :label="$t('imageThemeConfigBlock.imageBorderRadiusLabel')"
          :error="fieldHasErrors('image_border_radius')"
        >
          <FormInput
            v-model="values.image_border_radius"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`image_border_radius`]
            "
            :error="fieldHasErrors('image_border_radius')"
            type="number"
            :min="0"
            :max="100"
            remove-number-input-controls
            :placeholder="
              $t('imageThemeConfigBlock.imageBorderRadiusPlaceholder')
            "
            :to-value="(value) => (value ? parseInt(value) : null)"
          >
            <template #suffix>px</template>
          </FormInput>

          <template #after-input>
            <ResetButton
              v-model="values.image_border_radius"
              :default-value="theme?.image_border_radius"
            />
          </template>

          <template #error>
            {{ v$.values.image_border_radius.$errors[0].$message }}
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
import { IMAGE_SOURCE_TYPES } from '@baserow/modules/builder/enums'
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
  image_border_radius: {
    min: 0,
    max: 100,
  },
}

export default {
  name: 'ImageThemeConfigBlock',
  components: {
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
        image_border_radius: this.theme?.image_border_radius,
      },
      allowedValues: [
        'image_alignment',
        'image_max_width',
        'image_max_height',
        'image_constraint',
        'image_border_radius',
      ],
      defaultValuesWhenEmpty: {
        image_min_width: minMax.image_width.min,
        image_min_height: minMax.image_height.min,
        image_border_radius: minMax.image_border_radius.min,
      },
    }
  },
  computed: {
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
        image_border_radius: {
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', {
              min: minMax.image_border_radius.min,
            }),
            minValue(minMax.image_border_radius.min)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.minValueField', {
              min: minMax.image_border_radius.max,
            }),
            minValue(minMax.image_border_radius.min)
          ),
        },
      },
    }
  },
}
</script>
