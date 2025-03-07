<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      horizontal
      required
      :label="$t('positionedContainerElementForm.alignmentLabel')"
      class="margin-bottom-2"
    >
      <Dropdown
        :value="values.alignment"
        :show-search="false"
        @input="onValuesChanged"
      >
        <DropdownItem
          v-for="alignment in alignmentTypes"
          :key="alignment.value"
          :name="alignment.label"
          :value="alignment.value"
        />
      </Dropdown>
    </FormGroup>
  </form>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import { mapActions, mapGetters } from 'vuex'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import CustomStyle from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyle'
import { PAGE_ALIGNMENTS } from '@baserow/modules/builder/enums'

export default {
  name: 'PositionedContainerElementForm',
  components: { CustomStyle },
  mixins: [elementForm],
  data() {
    return {
      values: {
        alignment: '',
        styles: {},
      },
      allowedValues: [
        'alignment',
        'styles',
      ],
    }
  },
  computed: {
    ...mapGetters({
      getRootElements: 'element/getRootElements',
      getElementSelected: 'element/getSelected',
    }),
    element() {
      return this.getElementSelected(this.builder)
    },
    rootElements() {
      return this.getRootElements(this.currentPage)
    },
    alignmentTypes() {
      return [
        {
          label: this.$t('positionedContainerElementForm.alignmentTop'),
          value: PAGE_ALIGNMENTS.TOP,
        },
        {
          label: this.$t('positionedContainerElementForm.alignmentBottom'),
          value: PAGE_ALIGNMENTS.BOTTOM,
        },
      ]
    },
  },
  methods: {
    ...mapActions({
      actionMoveElement: 'element/move',
    }),
    async onValuesChanged(event) {
      let beforeElementId = null
      if (event === PAGE_ALIGNMENTS.TOP) {
        beforeElementId = this.rootElements.at(0).id
      }
      
      try {
        await this.actionMoveElement({
          builder: this.builder,
          page: this.currentPage,
          elementId: this.element.id,
          beforeElementId,
        })
        this.values.alignment = event
      } catch (error) {
        notifyIf(error)
      }
    }
  }
}
</script>
