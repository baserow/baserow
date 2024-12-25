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
          <HorizontalAlignmentsSelector v-model="values.image_alignment" />

          <template #after-input>
            <ResetButton
              v-model="values.image_alignment"
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
          :error-message="
            $v.values.image_max_width.$dirty &&
            !$v.values.image_max_width.integer
              ? $t('error.integerField')
              : !$v.values.image_max_width.minValue
              ? $t('error.minValueField', { min: 0 })
              : !$v.values.image_max_width.maxValue
              ? $t('error.maxValueField', { max: 100 })
              : !$v.values.image_max_width.required
              ? $t('error.requiredField')
              : ''
          "
        >
          <FormInput
            v-model="values.image_max_width"
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
              v-model="values.image_max_width"
              :default-value="theme?.image_max_width"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          required
          :label="$t('imageThemeConfigBlock.maxHeightLabel')"
          class="margin-bottom-2"
          :error-message="
            $v.values.image_max_height.$dirty &&
            !$v.values.image_max_height.integer
              ? $t('error.integerField')
              : !$v.values.image_max_height.minValue
              ? $t('error.minValueField', { min: 5 })
              : !$v.values.image_max_height.maxValue
              ? $t('error.maxValueField', { max: 3000 })
              : ''
          "
        >
          <FormInput
            v-model="imageMaxHeight"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`image_min_height`]
            "
            type="number"
            remove-number-input-controls
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
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('imageThemeConfigBlock.imageConstraintsLabel')"
        >
          <Dropdown
            v-model="values.image_constraint"
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
      </template>
      <template #preview>
        <ABImage src="/img/favicon_192.png" />
      </template>
    </ThemeConfigBlockSection>
  </div>
</template>

<script>
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'
import { IMAGE_SOURCE_TYPES } from '@baserow/modules/builder/enums'
import { integer, maxValue, minValue, required } from 'vuelidate/lib/validators'

const minMax = {
  image_width: {
    min: 0,
    max: 100,
  },
  image_height: {
    min: 5,
    max: 3000,
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
  data() {
    return {
      values: {},
      allowedValues: [
        'image_alignment',
        'image_max_width',
        'image_max_height',
        'image_constraint',
      ],
      defaultValuesWhenEmpty: {
        image_min_width: minMax.image_width.min,
        image_min_height: minMax.image_height.min,
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
        if (!newValue && this.values.image_constraint === 'cover') {
          this.values.image_constraint = 'contain'
        }
        // If the `image_max_height` is set, and the
        // constraint is 'contain', then reset back to 'cover'.
        if (newValue && this.values.image_constraint === 'contain') {
          this.values.image_constraint = 'cover'
        }
        this.values.image_max_height = newValue
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
          this.values.image_max_height = null
        }
        if (value === 'cover') {
          // Set the height to what is defined in theme
          this.values.image_max_height = this.theme.image_max_height
        }
        this.values.image_constraint = value
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
        return !this.values.image_max_height
      } else if (name === 'contain') {
        return !!(
          this.values.image_max_height && this.values.image_max_height > 0
        )
      }
    },
    isAllowedKey(key) {
      return key.startsWith('image_')
    },
  },
  validations: {
    values: {
      image_max_width: {
        required,
        integer,
        minValue: minValue(minMax.image_width.min),
        maxValue: maxValue(minMax.image_width.max),
      },
      image_max_height: {
        integer,
        minValue: minValue(minMax.image_height.min),
        maxValue: maxValue(minMax.image_height.max),
      },
    },
  },
}
</script>
