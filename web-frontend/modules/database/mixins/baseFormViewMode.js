import { clone } from '@baserow/modules/core/utils/object'

export default {
  props: {
    modelValue: {
      type: Object,
      required: true,
    },
    loading: {
      type: Boolean,
      required: true,
    },
    submitted: {
      type: Boolean,
      required: true,
    },
    title: {
      type: String,
      required: true,
    },
    description: {
      type: String,
      required: true,
    },
    coverImage: {
      validator: (prop) => typeof prop === 'object' || prop === null,
      required: true,
    },
    logoImage: {
      validator: (prop) => typeof prop === 'object' || prop === null,
      required: true,
    },
    submitText: {
      type: String,
      required: true,
    },
    isRedirect: {
      type: Boolean,
      required: true,
    },
    submitActionRedirectUrl: {
      type: String,
      required: true,
    },
    submitActionMessage: {
      type: String,
      required: true,
    },
    allFields: {
      type: Array,
      required: true,
    },
    visibleFields: {
      type: Array,
      required: true,
    },
    showLogo: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['submit', 'update:modelValue'],
  data() {
    return {
      // We need to make a copy of the values because we must change the values and
      // it's not possible to update a prop.
      values: clone(this.modelValue),
    }
  },
  methods: {
    updateValue(key, value) {
      this.values[key] = value
      this.$emit('update:modelValue', this.values)
    },
  },
}
