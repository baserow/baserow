<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyle
      v-model="values.styles"
      style-key="menu"
      :config-block-types="['button', 'link']"
      :theme="builder.theme"
      :extra-args="{ noAlignment: true, noWidth: true }"
    />
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

    <FormGroup
      :label="$t('menuElementForm.alignment')"
      small-label
      required
      class="margin-bottom-2"
    >
      <HorizontalAlignmentsSelector v-model="values.alignment" />
    </FormGroup>

    <div
      ref="menuItemAddContainer"
      class="menu-element-form__add-item-container"
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
    <p v-if="!values.menu_items.length">
      {{ $t('menuElementForm.noMenuItemsMessage') }}
    </p>
    <Context ref="menuItemAddContext" :hide-on-click-outside="true">
      <div class="menu-element-form__add-item-context">
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
    <div>
      <div v-for="item in values.menu_items" :key="item.uid" ref="menuItems">
        <MenuElementItemForm
          :default-values="item"
          @remove-item="removeMenuItem($event)"
          @values-changed="updateMenuItem"
        ></MenuElementItemForm>
      </div>
    </div>
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import {
  HORIZONTAL_ALIGNMENTS,
  ORIENTATIONS,
} from '@baserow/modules/builder/enums'
import {
  getNextAvailableNameInSequence,
  uuid,
} from '@baserow/modules/core/utils/string'
import { mapGetters } from 'vuex'
import MenuElementItemForm from '@baserow/modules/builder/components/elements/components/forms/general/MenuElementItemForm'
import CustomStyle from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyle'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'
import sortableDirective from '@baserow/modules/core/directives/sortable'

export default {
  name: 'MenuElementForm',
  components: {
    MenuElementItemForm,
    CustomStyle,
    HorizontalAlignmentsSelector,
  },
  mixins: [elementForm],
  data() {
    return {
      values: {
        value: '',
        styles: {},
        orientation: ORIENTATIONS.VERTICAL,
        alignment: HORIZONTAL_ALIGNMENTS.LEFT,
        menu_items: [],
      },
      allowedValues: [
        'value',
        'styles',
        'menu_items',
        'orientation',
        'alignment',
      ],
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
        {
          icon: 'baserow-icon-spacer',
          label: this.$t('menuElementForm.menuItemAddSpacer'),
          type: 'spacer',
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
  mounted() {
    /**
     * Using the `v-sortable` directive doesn't work when the v-for loop and
     * elements being iterated over are in different components.
     *
     * This ensures that the sortable directive is applied to the elements
     * once the MenuElementItemForm components have been mounted.
     */
    this.$nextTick(() => {
      this.initializeSortable()
    })
  },
  beforeDestroy() {
    this.cleanUpSortable()
  },
  methods: {
    /**
     * Programmatically apply sortable to each child menu item. This mimics
     * how the v-sortable directive behaves.
     */
    initializeSortable() {
      if (this.$refs.menuItems && this.$refs.menuItems.length > 0) {
        this.$refs.menuItems.forEach((menuItem, index) => {
          this.makeSortable(menuItem, this.values.menu_items[index].uid)
        })
      }
    },
    /**
     * Create a sortable directive and bind it to the element.
     */
    makeSortable(element, uid) {
      const binding = {
        value: {
          id: uid,
          update: this.reorderMenuItems,
          enabled: this.$hasPermission(
            'builder.page.element.update',
            this.element,
            this.workspace.id
          ),
          handle: '[data-sortable-handle-root]',
        },
        def: sortableDirective,
      }

      sortableDirective.bind(element, binding)

      // Store the bindings so they can be cleaned up in beforeDestroy()
      element._sortableBinding = binding
    },
    /**
     * Clean up all sortable bindings when the component is destroyed.
     */
    cleanUpSortable() {
      if (this.$refs.menuItems) {
        this.$refs.menuItems.forEach((element) => {
          if (element._sortableBinding) {
            sortableDirective.unbind(element, element._sortableBinding)
          }
        })
      }
    },
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
          parent_menu_item: null, // This is the root menu item.
        },
      ]
      this.$refs.menuItemAddContext.hide()

      // Since the menu_items array has changed, the elements need to be
      // bound to the sortable directive.
      this.$nextTick(() => {
        this.cleanUpSortable()
        this.initializeSortable()
      })
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
    reorderMenuItems(newOrder) {
      const itemsByUid = Object.fromEntries(
        this.values.menu_items.map((item) => [item.uid, item])
      )
      this.values.menu_items = newOrder.map((uid) => itemsByUid[uid])
    },
  },
}
</script>
