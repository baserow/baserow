<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyle
      v-model="values.styles"
      style-key="button"
      :config-block-types="['button']"
      :theme="builder.theme"
    />

    <FormSection
      class="margin-bottom-2"
      :title="$t('menuElementForm.orientationLabel')"
    >
      <RadioButton
        v-model="values.orientation"
        icon="iconoir-view-columns-3"
        :value="MENU_ORIENTATION.HORIZONTAL"
      >
        {{ $t('menuElementForm.orientationHorizontal') }}
      </RadioButton>
      <RadioButton
        v-model="values.orientation"
        icon="iconoir-table-rows"
        :value="MENU_ORIENTATION.VERTICAL"
      >
        {{ $t('menuElementForm.orientationVertical') }}
      </RadioButton>
    </FormSection>

    <div class="menu-element__add-item-container">
      <div>
        {{ $t('menuElementForm.menuItemsLabel') }}
      </div>
      <div>
        <ButtonText
          type="primary"
          icon="iconoir-plus"
          size="small"
          @click="addMenuItem"
        >
          {{ $t('menuElementForm.addMenuItemLink') }}
        </ButtonText>
      </div>
    </div>

    <div v-for="(item, index) in values.menu_items" :key="item.id">
      <Expandable
        v-sortable="{
          id: item.id,
          update: orderMenuItems,
          enabled: $hasPermission(
            'builder.page.element.update',
            element,
            workspace.id
          ),
          handle: '[data-sortable-handle]',
        }"
        class="table-element-form__field"
      >
        <template #header="{ toggle, expanded }">
          <div class="table-element-form__field-header" @click.stop="toggle">
            <div
              class="table-element-form__field-handle"
              data-sortable-handle
            />
            <div class="table-element-form__field-name">
              <i
                v-if="!expanded && menuItemInError(item)"
                class="table-element-form__field-error iconoir-warning-circle"
              ></i>
              {{ item.name }}
            </div>
            <i
              :class="
                expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'
              "
            />
          </div>
        </template>
        <template #default>
          <FormGroup
            small-label
            horizontal
            required
            :label="$t('menuElementForm.menuItemTypeLabel')"
            class="margin-bottom-2"
          >
            <Dropdown
              :value="item.type"
              :show-search="false"
              @input="changeItemType(item, $event)"
            >
              <DropdownItem
                v-for="itemType in menuItemTypes"
                :key="itemType.value"
                :name="itemType.label"
                :value="itemType.value"
              />
            </Dropdown>
          </FormGroup>

          <FormGroup
            small-label
            horizontal
            required
            :label="$t('menuElementForm.menuItemVariantLabel')"
            class="margin-bottom-2"
          >
            <Dropdown
              :value="item.menu_item_variant"
              :show-search="false"
              @input="changeItemVariant(item, $event)"
            >
              <DropdownItem
                v-for="itemVariant in menuItemVariants"
                :key="itemVariant.value"
                :name="itemVariant.label"
                :value="itemVariant.value"
              />
            </Dropdown>
          </FormGroup>

          <FormGroup
            small-label
            horizontal
            required
            class="margin-bottom-2"
            :label="$t('menuElementForm.menuItemLabelLabel')"
            :error-message="
              !$v.values.menu_items.$each[index].name.required
                ? $t('error.requiredField')
                : !$v.values.menu_items.$each[index].name.maxLength
                ? $t('error.maxLength', { max: 255 })
                : ''
            "
          >
            <FormInput
              v-model="item.name"
              class="table-element-form__field-label"
            >
            </FormInput>
            <template v-if="values.menu_items.length > 1" #after-input>
              <ButtonIcon icon="iconoir-bin" @click="removeMenuItem(item)" />
            </template>
          </FormGroup>

          <LinkNavigationSelectionForm
            :default-values="item"
            @values-changed="updateItem(item, $event)"
          />
        </template>
      </Expandable>
    </div>
  </form>
</template>

<script>
import { required, maxLength } from 'vuelidate/lib/validators'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import CustomStyle from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyle'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import { MENU_ORIENTATION } from '@baserow/modules/builder/enums'
import {
  getNextAvailableNameInSequence,
  uuid,
} from '@baserow/modules/core/utils/string'
import LinkNavigationSelectionForm from '@baserow/modules/builder/components/elements/components/forms/general/LinkNavigationSelectionForm'
import { mapGetters } from 'vuex'

export default {
  name: 'MenuElementForm',
  components: {
    InjectedFormulaInput,
    CustomStyle,
    LinkNavigationSelectionForm,
  },
  mixins: [elementForm],
  data() {
    return {
      values: {
        value: '',
        styles: {},
        menu_items: [],
      },
      allowedValues: ['value', 'styles', 'menu_items'],
    }
  },
  computed: {
    ...mapGetters({
      getElementSelected: 'element/getSelected',
    }),
    MENU_ORIENTATION() {
      return MENU_ORIENTATION
    },
    menuItemTypes() {
      return [
        {
          label: this.$t('menuElementForm.menuItemTypeItem'),
          value: 'item',
        },
        {
          label: this.$t('menuElementForm.menuItemTypeSeparator'),
          value: 'separator',
        },
      ]
    },
    menuItemVariants() {
      return [
        {
          label: this.$t('menuElementForm.menuItemVariantLink'),
          value: 'link',
        },
        {
          label: this.$t('menuElementForm.menuItemVariantButton'),
          value: 'button',
        },
      ]
    },
    element() {
      return this.getElementSelected(this.builder)
    },
  },
  methods: {
    async addMenuItem() {
      this.values.menu_items.push({
        name: getNextAvailableNameInSequence(
          this.$t('menuElementForm.menuItemDefaultName'),
          this.values.menu_items.map(({ name }) => name)
        ),
        menu_item_variant: 'link',
        value: '',
        type: 'item',
        parent_menu_item: null,
        uid: uuid(),
      })
    },
    changeItemType(itemToUpdate, newType) {
      this.values.menu_items = this.values.menu_items.map((item) => {
        if (item.id === itemToUpdate.id) {
          return {
            id: item.id,
            uid: uuid(),
            name: item.name,
            menu_item_variant: item.menu_item_variant,
            value: item.value,
            parent_menu_item: item.parent_menu_item,
            type: newType,
          }
        }
        return item
      })
    },
    changeItemVariant(itemToUpdate, newVariant) {
      this.values.menu_items = this.values.menu_items.map((item) => {
        if (item.id === itemToUpdate.id) {
          return {
            id: item.id,
            uid: uuid(),
            name: item.name,
            menu_item_variant: newVariant,
            value: item.value,
            parent_menu_item: item.parent_menu_item,
            type: item.type,
          }
        }
        return item
      })
    },
    orderMenuItems(newOrder) {
      // TODO
    },
    menuItemInError(item) {
      // TODO
      return false
    },
    removeMenuItem(menuItem) {
      this.values.menu_items = this.values.menu_items.filter(
        (item) => item !== menuItem
      )
    },
    updateItem(menuItem, values) {
      console.log('got a request to updatee the field..: ', values)
      this.values.menu_items = this.values.menu_items.map((item) => {
        if (item.id === menuItem.id) {
          return { ...item, ...values }
        }
        return item
      })
    },
  },
  validations() {
    return {
      values: {
        menu_items: {
          $each: {
            name: {
              required,
              maxLength: maxLength(225),
            },
          },
        },
      },
    }
  },
}
</script>
