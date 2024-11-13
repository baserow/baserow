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
          <HorizontalAlignmentsSelector v-model="v$.image_alignment.$model" />

          <template #after-input>
            <ResetButton
              v-model="v$.image_alignment.$model"
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
          :error="v$.image_max_width.$error"
        >
          <FormInput
            v-model="v$.image_max_width.$model"
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
              v-model="v$.image_max_width.$model"
              :default-value="theme?.image_max_width"
            />
          </template>

          <template #error>
            <span v-if="v$.image_max_width.integer.$invalid">
              {{ $t('error.integerField') }}
            </span>
            <span v-else-if="v$.image_max_width.minValue.$invalid">
              {{ $t('error.minValueField', { min: 0 }) }}
            </span>
            <span v-else-if="v$.image_max_width.maxValue.$invalid">
              {{ $t('error.maxValueField', { max: 100 }) }}
            </span>
            <span v-else-if="v$.image_max_width.required.$invalid">
              {{ $t('error.requiredField') }}
            </span>
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          required
          :label="$t('imageThemeConfigBlock.maxHeightLabel')"
          class="margin-bottom-2"
          :error="v$.image_max_height.$error"
        >
          <FormInput
            v-model="imageMaxHeight"
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

          <template #error>
            <span v-if="v$.image_max_height.integer.$invalid">
              {{ $t('error.integerField') }}
            </span>
            <span v-else-if="v$.image_max_height.minValue.$invalid">
              {{ $t('error.minValueField', { min: 5 }) }}
            </span>
            <span v-else-if="v$.image_max_height.maxValue.$invalid">
              {{ $t('error.maxValueField', { max: 3000 }) }}
            </span>
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
            v-model="v$.image_constraint"
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
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'
import { IMAGE_SOURCE_TYPES } from '@baserow/modules/builder/enums'
import { integer, maxValue, minValue, required } from '@vuelidate/validators'

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
      v$: null,
      values: null,
      allowedValues: [
        'image_alignment',
        'image_max_width',
        'image_max_height',
        'image_constraint',
      ],
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
        if (!newValue && this.v$.image_constraint.$model === 'cover') {
          this.v$.image_constraint.$model = 'contain'
        }
        // If the `image_max_height` is set, and the
        // constraint is 'contain', then reset back to 'cover'.
        if (newValue && this.v$.image_constraint.$model === 'contain') {
          this.v$.image_constraint.$model = 'cover'
        }
        this.v$.image_max_height.$model = newValue
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
          this.v$.image_max_height.$model = null
        }
        if (value === 'cover') {
          // Set the height to what is defined in theme
          this.v$.image_max_height.$model = this.theme.image_max_height
        }
        this.v$.image_constraint.$model = value
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
  created() {
    const values = reactive({
      image_alignment: this.theme?.image_alignment,
      image_max_width: this.theme?.image_max_width,
      image_max_height: this.theme?.image_max_height,
      image_constraint: this.theme?.image_constraint,
    })

    const rules = computed(() => ({
      image_max_width: {
        required,
        integer,
        minValue: minValue(0),
        maxValue: maxValue(100),
      },
      image_max_height: {
        integer,
        minValue: minValue(5),
        maxValue: maxValue(3000),
      },
      image_constraint: {},
      image_alignment: {},
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  methods: {
    constraintDisabled(name) {
      if (name === 'cover') {
        return !this.v$.image_max_height.$model
      } else if (name === 'contain') {
        return !!(
          this.v$.image_max_height.$model && this.v$.image_max_height.$model > 0
        )
      }
    },
    isAllowedKey(key) {
      return key.startsWith('image_')
    },
  },
}
</script>
