<template>
  <div class="rating-element">
    <ABFormGroup
      v-if="editable"
      :label="labelResolved"
      :required="element.required"
      :error-message="displayFormDataError ? $t('error.requiredField') : ''"
    >
      <div class="rating" :style="{ '--rating-color': element.color }">
        <Rating
          :value="displayValue"
          :max-value="maxValue"
          :color="'custom'"
          :rating-style="element.style || 'star'"
          :read-only="false"
          :show-unselected-in-read-only="true"
          @update="onUpdate"
        />
      </div>
    </ABFormGroup>
    <div v-else class="rating" :style="{ '--rating-color': element.color }">
      <Rating
        :value="resolvedValue"
        :max-value="maxValue"
        :color="'custom'"
        :rating-style="element.style || 'star'"
        :read-only="true"
        :show-unselected-in-read-only="true"
      />
    </div>
  </div>
</template>

<script>
import Rating from '@baserow/modules/database/components/Rating'
import element from '@baserow/modules/builder/mixins/element'
import formElement from '@baserow/modules/builder/mixins/formElement'

export default {
  name: 'RatingInputElement',
  components: {
    Rating,
  },
  mixins: [element, formElement],
  props: {
    element: {
      type: Object,
      required: true,
    },
    editable: {
      type: Boolean,
      default: true,
    },
  },
  computed: {
    resolvedValue() {
      const value = this.resolveFormula(this.element.value)
      return value ? Number(value) : 0
    },
    maxValue() {
      return Number(this.element.max_value) || 5
    },
    labelResolved() {
      return this.resolveFormula(this.element.label)
    },
    displayValue() {
      if (!this.editable) {
        return this.resolvedValue
      }
      return this.formElementData?.value ?? this.resolvedValue
    },
  },
  mounted() {
    if (this.editable) {
      this.setFormData(this.resolvedValue)
    }
  },
  methods: {
    onUpdate(value) {
      if (this.editable) {
        this.handleFormElementChange(value)
      }
    },
  },
  watch: {
    resolvedValue: {
      handler(newValue) {
        if (this.editable && this.formElementData?.value === undefined) {
          this.setFormData(newValue)
        }
      },
    },
  },
}
</script>

<style lang="scss">
@import '@baserow/modules/core/assets/scss/colors';
@import '@baserow/modules/core/assets/scss/placeholders';
@import '@baserow/modules/core/assets/scss/mixins/helpers';
@import '@baserow/modules/core/assets/scss/components/rating';

.rating-element {
  display: inline-block;

  .rating {
    .rating__star.rating__star {
      color: var(--rating-color) !important;
      opacity: 0.3;

      &.rating__star--selected {
        opacity: 1;
      }
    }

    &.editing {
      .rating__star.rating__star:hover {
        opacity: 1;

        ~ .rating__star {
          opacity: 0.3;
        }
      }

      &:hover .rating__star.rating__star {
        opacity: 1;
      }
    }
  }
}
</style>
