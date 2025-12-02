<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyleButton
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
      v-if="values.orientation === ORIENTATIONS.HORIZONTAL"
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
    <div class="menu-element-form__items">
      <MenuElementItemForm
        v-for="(item, index) in values.menu_items"
        :key="`${item.uid}-${index}`"
        v-sortable="{
          id: item.uid,
          update: orderRootItems,
          enabled: $hasPermission(
            'builder.page.element.update',
            element,
            workspace.id
          ),
          handle: '[data-sortable-handle]',
        }"
        :icon="getIcon(item.type)"
        :default-values="item"
        @remove-item="removeMenuItem($event)"
        @values-changed="updateMenuItem"
      />
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
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'

export default {
  name: 'MenuElementForm',
  components: {
    MenuElementItemForm,
    CustomStyleButton,
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
  methods: {
    getIcon(itemType) {
      return this.addMenuItemTypes.find(({ type }) => type === itemType).icon
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
    /**
     * Responsible for sorting the root items of this menu item.
     */
    orderRootItems(newOrder) {
      const itemsByUid = Object.fromEntries(
        this.values.menu_items.map((item) => [item.uid, item])
      )
      this.values.menu_items = newOrder.map((uid) => itemsByUid[uid])
    },
  },
}
</script>
