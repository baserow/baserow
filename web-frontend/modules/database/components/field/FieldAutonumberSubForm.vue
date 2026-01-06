<script>
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'

export default {
  name: 'FieldAutonumberSubForm',
  mixins: [form, fieldSubForm],
  setup() {
    return () => null
  },
  data() {
    return {
      allowedValues: ['view_id'],
      values: { view_id: null },
    }
  },
  methods: {
    getDefaultValues() {
      return {
        view_id: this.view.id,
      }
    },
  },
}
</script>
