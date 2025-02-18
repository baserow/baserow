<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyle
      v-model="values.styles"
      style-key="button"
      :config-block-types="['button']"
      :theme="builder.theme"
    />

    <FormGroup
      :label="$t('repeatElementForm.orientationLabel')"
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

    <div
      v-for="(item, index) in values.menu_items.filter(
        (item) => item.parent_menu_item === null
      )"
      :key="item.uid"
    >
      <Expandable
        v-sortable="{
          id: item.uid,
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
              <template v-if="item.type === 'separator'">
                {{ $t('menuElement.separator') }}
              </template>
              <template v-else>
                {{ getResolvedName(item.name) }}
              </template>
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

            <template #after-input>
              <ButtonIcon icon="iconoir-bin" @click="removeMenuItem(item)" />
            </template>
          </FormGroup>

          <div v-if="item.type !== 'separator'">
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
              <InjectedFormulaInput
                v-model="item.name"
                :placeholder="$t('menuElementForm.namePlaceholder')"
              />
            </FormGroup>

            <div v-if="item.menu_item_variant === 'link'">
              <LinkNavigationSelectionForm
                :default-values="item"
                @values-changed="updateItem(item, $event)"
              />

              <div v-if="item.children && item.children.length > 0">
                <div v-for="(child, childIndex) in item.children" :key="child.uid">
                  <Expandable class="menu-element__sub-link-form">
                    <template #header="{ toggle, expanded }">
                      <div
                        class="menu-element__sub-link-form__header"
                        @click.stop="toggle"
                      >
                        <div
                          class="menu-element__sub-link-form__handle"
                          data-sortable-handle
                        />
                        <div class="menu-element__sub-link-form__name">
                          <i
                            v-if="!expanded && menuItemInError(child)"
                            class="menu-element__sub-link-form__error iconoir-warning-circle"
                          ></i>
                          {{ getResolvedName(child.name) }}
                        </div>
                        <i
                          :class="
                            expanded
                              ? 'iconoir-nav-arrow-down'
                              : 'iconoir-nav-arrow-right'
                          "
                        />
                      </div>
                    </template>

                    <template #default>
                      <FormGroup
                        small-label
                        horizontal
                        required
                        class="margin-bottom-2"
                        :label="$t('menuElementForm.menuItemLabelLabel')"
                        :error-message="
                          $v.values?.menu_items?.$each[index]?.children?.$each[
                            childIndex
                          ]?.name
                            ? !$v.values.menu_items.$each[index].children.$each[
                                childIndex
                              ].name.required
                              ? $t('error.requiredField')
                              : !$v.values.menu_items.$each[index].children.$each[
                                  childIndex
                                ].name.maxLength
                              ? $t('error.maxLength', { max: 255 })
                              : ''
                            : ''
                        "
                      >
                        <InjectedFormulaInput
                          v-model="child.name"
                          :placeholder="$t('menuElementForm.namePlaceholder')"
                        />
                        <template #after-input>
                          <ButtonIcon
                            icon="iconoir-bin"
                            @click="removeChildItem(item, child)"
                          />
                        </template>
                      </FormGroup>

                      <LinkNavigationSelectionForm
                        :default-values="child"
                        @values-changed="updateSubLink(child, $event)"
                      />
                    </template>
                  </Expandable>
                </div>
              </div>

              <div class="menu-element__menu-item-footer" />

              <div class="menu-element__add-sub-link-container">
                <ButtonText
                  type="primary"
                  icon="iconoir-plus"
                  size="small"
                  @click="addSubLink(item)"
                >
                  {{ $t('menuElementForm.addSubLink') }}
                </ButtonText>
              </div>
            </div>
          </div>
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
import { resolveFormula } from '@baserow/modules/core/formula'
import { ensureString } from '@baserow/modules/core/utils/validator'
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
        orientation: 'vertical',
        menu_items: [],
      },
      allowedValues: ['value', 'styles', 'menu_items', 'orientation'],
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
    orientationOptions() {
      return [
        {
          label: this.$t('menuElementForm.orientationVertical'),
          value: 'vertical',
          icon: 'iconoir-table-rows',
        },
        {
          label: this.$t('repeatElementForm.orientationHorizontal'),
          value: 'horizontal',
          icon: 'iconoir-view-columns-3',
        },
      ]
    },
  },
  methods: {
    async addMenuItem() {
      const name = getNextAvailableNameInSequence(
        this.$t('menuElementForm.menuItemDefaultName'),
        this.values.menu_items
          .filter((item) => item.parent_menu_item === null)
          .map(({ name }) => this.getResolvedName(name))
      )
      this.values.menu_items.push({
        name: `'${name}'`,
        menu_item_variant: 'link',
        value: '',
        type: 'item',
        parent_menu_item: null,
        uid: uuid(),
        children: [],
      })
    },
    getResolvedName(value) {
      return ensureString(resolveFormula(value))
    },
    changeItemType(itemToUpdate, newType) {
      this.values.menu_items = this.values.menu_items.map((item) => {
        if (item.uid === itemToUpdate.uid) {
          return {
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
      this.updateItem(itemToUpdate, { menu_item_variant: newVariant })
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
    removeChildItem(parent, child) {
      this.values.menu_items = this.values.menu_items.map((item) => {
        if (item.uid === parent.uid) {
          return {
            ...item,
            children: item.children.filter((c) => c.uid !== child.uid),
          }
        }
        return item
      })
    },
    updateItem(menuItem, values) {
      this.values.menu_items = this.values.menu_items.map((item) => {
        if (item.uid === menuItem.uid) {
          return { ...item, ...values }
        }
        return item
      })
    },
    updateSubLink(child, values) {
      this.values.menu_items = this.values.menu_items.map((item) => {
        if (item.children) {
          return {
            ...item,
            children: item.children.map((subItem) =>
              subItem.uid === child.uid ? { ...subItem, ...values } : subItem
            ),
          }
        }
        return item
      })
    },
    addSubLink(item) {
      const name = getNextAvailableNameInSequence(
        this.$t('menuElementForm.menuItemSubLinkDefaultName'),
        this.values.menu_items
          .filter((item) => item.parent_menu_item !== null)
          .map(({ name }) => this.getResolvedName(name))
      )
      const subItem = {
        name: `'${name}'`,
        menu_item_variant: 'link',
        type: 'item',
        uid: uuid(),
      }

      if (!Array.isArray(item.children)) {
        this.$set(item, 'children', [subItem])
      } else {
        this.$set(item.children, item.children.length, subItem)
      }
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
            children: {
              required: false,
              $each: {
                name: {
                  required,
                  maxLength: maxLength(225),
                },
              },
            },
          },
        },
      },
    }
  },
}
</script>
