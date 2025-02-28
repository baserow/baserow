<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      :label="$t('orientations.label')"
      small-label
      required
      class="margin-bottom-2"
    >
      <RadioGroup
        v-model="values.orientation"
        :options="orientationOptions"
        type="button"
      >
      </RadioGroup>
    </FormGroup>
    <div
      ref="menuItemAddContainer"
      class="menu-element__form--add-item-container"
    >
      <div>
        {{ $t('menuElementForm.menuItemsLabel') }}
      </div>
      <div>
        <ButtonText
          type="primary"
          icon="iconoir-plus"
          size="small"
          @click="
            $refs.menuItemAddContext.show(
              $refs.menuItemAddContainer,
              'bottom',
              'right'
            )
          "
        >
          {{ $t('menuElementForm.addMenuItemLink') }}
        </ButtonText>
      </div>
    </div>
    <Context ref="menuItemAddContext" :hide-on-click-outside="true">
      <div class="menu-element__form--add-item-context">
        <ButtonText
          v-for="(menuItemType, index) in addMenuItemTypes"
          :key="index"
          type="primary"
          :icon="menuItemType.icon"
          size="small"
          @click="addMenuItem(menuItemType.type)"
        >
          {{ menuItemType.label }}
        </ButtonText>
      </div>
    </Context>
    <div v-for="item in values.menu_items" :key="item.uid">
      <MenuElementItemForm
        :default-values="item"
        @remove-item="removeMenuItem($event)"
        @values-changed="updateMenuItem"
      ></MenuElementItemForm>
    </div>
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import { ORIENTATIONS } from '@baserow/modules/builder/enums'
import {
  getNextAvailableNameInSequence,
  uuid,
} from '@baserow/modules/core/utils/string'
import { mapGetters } from 'vuex'
import MenuElementItemForm from '@baserow/modules/builder/components/elements/components/forms/general/MenuElementItemForm'

export default {
  name: 'MenuElementForm',
  components: {
    MenuElementItemForm,
  },
  mixins: [elementForm],
  data() {
    return {
      values: {
        value: '',
        styles: {},
        orientation: ORIENTATIONS.VERTICAL,
        menu_items: [],
      },
      allowedValues: ['value', 'styles', 'menu_items', 'orientation'],
      addMenuItemTypes: [
        {
          icon: 'iconoir-link',
          label: this.$t('menuElementForm.menuItemAddLink'),
          type: 'link',
        },
        {
          icon: 'iconoir-cursor-pointer',
          label: this.$t('menuElementForm.menuItemAddButton'),
          type: 'button',
        },
        {
          icon: 'baserow-icon-separator',
          label: this.$t('menuElementForm.menuItemAddSeparator'),
          type: 'separator',
        },
      ],
    }
  },
  computed: {
    ...mapGetters({
      getElementSelected: 'element/getSelected',
    }),
    ORIENTATIONS() {
      return ORIENTATIONS
    },
    element() {
      return this.getElementSelected(this.builder)
    },
    orientationOptions() {
      return [
        {
          label: this.$t('orientations.vertical'),
          value: ORIENTATIONS.VERTICAL,
          icon: 'iconoir-table-rows',
        },
        {
          label: this.$t('orientations.horizontal'),
          value: ORIENTATIONS.HORIZONTAL,
          icon: 'iconoir-view-columns-3',
        },
      ]
    },
  },
  methods: {
    addMenuItem(type) {
      const name = getNextAvailableNameInSequence(
        this.$t('menuElementForm.menuItemDefaultName'),
        this.values.menu_items
          .filter((item) => item.parent_menu_item === null)
          .map(({ name }) => name)
      )

      this.values.menu_items = [
        ...this.values.menu_items,
        {
          name,
          variant: 'link',
          value: '',
          type,
          uid: uuid(),
          children: [],
        },
      ]
      this.$refs.menuItemAddContext.hide()
    },
    /**
     * When a menu item is removed, this method is responsible for removing it
     * from the `MenuElement` itself.
     */
    removeMenuItem(uidToRemove) {
      this.values.menu_items = this.values.menu_items.filter(
        (item) => item.uid !== uidToRemove
      )
    },
    /**
     * When a menu item is updated, this method is responsible for updating the
     * `MenuElement` with the new values.
     */
    updateMenuItem(newValues) {
      this.values.menu_items = this.values.menu_items.map((item) => {
        if (item.uid === newValues.uid) {
          return { ...item, ...newValues }
        }
        return item
      })
    },
  },
}
</script>
