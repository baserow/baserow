<template>
  <div>
    <div class="style-guide__wrapper">
      <Toasts></Toasts>
      <div class="style-guide">
        <div class="margin-bottom-3">
          <h1>&lt;h1&gt;Heading 1&lt;/h1&gt;</h1>
          <h2>&lt;h2&gt;Heading 2&lt;/h2&gt;</h2>
          <h3>&lt;h3&gt;Heading 3&lt;/h3&gt;</h3>
          <h4>&lt;h4&gt;Heading 4&lt;/h4&gt;</h4>
        </div>
        <div class="margin-bottom-3">
          <p>
            Lorem ipsum dolor sit amet, <a href="#">consectetur</a> adipiscing
            elit. Pellentesque eget ipsum eu risus congue posuere vel at erat.
            Phasellus mattis est sit amet dui sodales, a interdum turpis
            interdum. Sed eu lobortis libero. Phasellus
            <strong>vestibulum</strong>, nunc sed elementum scelerisque, tellus
            felis pretium lectus, eget laoreet quam est in massa. Maecenas non
            dapibus dolor. Mauris <em>condimentum</em> iaculis dui vel finibus.
            Nullam consequat non arcu at vehicula. Maecenas ac consequat ipsum,
            sed viverra dui. Donec dignissim suscipit ultrices. Nullam quis
            mattis nulla, et venenatis justo. Curabitur scelerisque dictum
            <a href="#">velit</a>, eget vestibulum lacus gravida in. Praesent id
            lorem volutpat, venenatis quam vel, ultricies leo.
          </p>
        </div>
        <div class="margin-bottom-3">
          <FormTextarea
            ref="input"
            placeholder="Textarea"
            class="margin-bottom-2"
            value=""
            :rows="6"
          />

          <FormTextarea
            ref="input"
            auto-expandable
            placeholder="Auto expandable textarea"
            class="margin-bottom-2"
            :max-rows="14"
            value=""
          />

          <FormInput
            disabled
            placeholder="Enter something here"
            value="This is the value"
            icon-right="iconoir-clock"
            class="margin-bottom-2"
          />

          <FormInput
            v-model="input"
            placeholder="Error state"
            error
            icon-left="iconoir-search"
            class="margin-bottom-2"
          />

          <FormInput
            v-model="input"
            placeholder="Loading state..."
            loading
            class="margin-bottom-2"
          />

          <FormInput
            v-model="input"
            placeholder="Left icon"
            icon-left="iconoir-search"
            class="margin-bottom-2"
          />

          <FormInput
            v-model="input"
            placeholder="Right icon"
            icon-right="iconoir-db"
            class="margin-bottom-2"
          />

          <FormInput
            v-model="input"
            size="small"
            placeholder="Small input"
            icon-right="iconoir-db"
            class="margin-bottom-2"
          />

          <FormInput
            v-model="input"
            size="large"
            placeholder="Large input"
            icon-right="iconoir-db"
            class="margin-bottom-2"
          />

          <FormGroup class="margin-bottom-2" label="Form Group">
            <FormInput
              ref="name"
              v-model="input"
              type="text"
              placeholder="Native input"
            />
            <template #helper>Description text</template>
          </FormGroup>

          <FormGroup
            class="margin-bottom-2"
            label="Form Group error"
            :error="true"
            required
          >
            <FormInput
              ref="name"
              v-model="input"
              :error="true"
              placeholder="Native input"
            />
            <template #helper>Description text</template>
            <template #error>Error message</template>
          </FormGroup>

          <FormGroup label="Checkbox field" required class="margin-bottom-3">
            <Checkbox v-model="checkbox" class="margin-bottom-1"></Checkbox>
            <Checkbox v-model="checkbox">With text</Checkbox>
          </FormGroup>

          <FormGroup
            class="margin-bottom-3"
            label="Native Radio input"
            required
          >
            <RadioGroup v-model="radio" :options="radioOptions"> </RadioGroup>
          </FormGroup>

          <FormGroup class="margin-bottom-3" label="Radio buttons" required>
            <RadioGroup v-model="radio" type="button" :options="radioOptions">
            </RadioGroup>
          </FormGroup>

          <FormGroup
            class="margin-bottom-3"
            label="Radio buttons with icons"
            required
          >
            <RadioGroup
              v-model="radio"
              type="button"
              :options="radioOptionIcons"
            >
            </RadioGroup>
          </FormGroup>

          <FormGroup label="Switch Input" class="margin-bottom-3" required>
            <SwitchInput
              v-model="switchValue"
              class="margin-bottom-2"
            ></SwitchInput>
            <SwitchInput v-model="switchValue" class="margin-bottom-2"
              >With text</SwitchInput
            >
            <SwitchInput v-model="switchUnknown" class="margin-bottom-2"
              >With text</SwitchInput
            >
            <SwitchInput v-model="switchUnknown" small class="margin-bottom-2"
              >Small With text</SwitchInput
            >
            <SwitchInput
              v-model="switchValue"
              class="margin-bottom-2"
              small
            ></SwitchInput>
            <SwitchInput v-model="switchValue" class="margin-bottom-1" large>
              Small with text
            </SwitchInput>
            <SwitchInput
              v-model="switchUnknown"
              class="margin-bottom-2"
              disabled
            >
              Disabled
            </SwitchInput>
            <SwitchInput
              v-model="switchUnknown"
              class="margin-bottom-2"
              disabled
              small
            >
              Small disabled
            </SwitchInput>
            <SwitchInput
              v-model="switchValue"
              color="neutral"
              class="margin-bottom-2"
              >Neutral color</SwitchInput
            >
            <SwitchInput
              v-model="switchUnknown"
              color="neutral"
              class="margin-bottom-2"
              >Neutral intermediate</SwitchInput
            >
            <SwitchInput
              v-model="switchValue"
              color="neutral"
              :disabled="true"
              class="margin-bottom-2"
              >Neutral disabled</SwitchInput
            >
          </FormGroup>

          <FormGroup label="Dropdown" required class="margin-bottom-2">
            <div style="width: 200px">
              <Dropdown v-model="dropdown">
                <DropdownItem name="Choice 1" value="choice-1"></DropdownItem>
                <DropdownItem
                  name="Choice 2"
                  value="choice-2"
                  icon="iconoir-edit-pencil"
                  description="Lorem ipsum dolor sit amet, consectetur."
                ></DropdownItem>
                <DropdownItem
                  name="Choice 3"
                  value="choice-3"
                  icon="iconoir-db"
                ></DropdownItem>
                <DropdownItem
                  name="Choice 4"
                  value="choice-4"
                  icon="iconoir-cancel"
                  :disabled="true"
                ></DropdownItem>
                <DropdownItem
                  name="Choice 5"
                  value="choice-5"
                  icon="iconoir-edit-pencil"
                  description="Lorem ipsum dolor sit amet, consectetur."
                ></DropdownItem>
                <DropdownItem
                  name="Choice 6"
                  value="choice-6"
                  icon="iconoir-edit-pencil"
                  description="Lorem ipsum dolor sit amet, consectetur."
                ></DropdownItem>
              </Dropdown>
            </div>
          </FormGroup>

          <FormGroup label="Dropdown multiple" required class="margin-bottom-2">
            <div style="width: 200px">
              <Dropdown v-model="dropdownMultiple" multiple>
                <DropdownItem name="Choice 1" value="choice-1"></DropdownItem>
                <DropdownItem
                  name="Choice 2"
                  value="choice-2"
                  icon="iconoir-edit-pencil"
                  description="Lorem ipsum dolor sit amet, consectetur."
                ></DropdownItem>
                <DropdownItem
                  name="Choice 3"
                  value="choice-3"
                  icon="iconoir-db"
                ></DropdownItem>
                <DropdownItem
                  name="Choice 4"
                  value="choice-4"
                  icon="iconoir-cancel"
                  :disabled="true"
                ></DropdownItem>
                <DropdownItem
                  name="Choice 5"
                  value="choice-5"
                  icon="iconoir-edit-pencil"
                  description="Lorem ipsum dolor sit amet, consectetur."
                ></DropdownItem>
                <DropdownItem
                  name="Choice 6"
                  value="choice-6"
                  icon="iconoir-edit-pencil"
                  description="Lorem ipsum dolor sit amet, consectetur."
                ></DropdownItem>
              </Dropdown>
            </div>
          </FormGroup>

          <FormGroup label="Dropdown disabled" required class="margin-bottom-2">
            <div style="width: 200px">
              <Dropdown v-model="dropdown" disabled>
                <DropdownItem name="Choice 1" value="choice-1"></DropdownItem>
                <DropdownItem
                  name="Choice 2"
                  value="choice-2"
                  icon="iconoir-edit-pencil"
                  description="Lorem ipsum dolor sit amet, consectetur."
                ></DropdownItem>
                <DropdownItem
                  name="Choice 3"
                  value="choice-3"
                  icon="iconoir-db"
                ></DropdownItem>
                <DropdownItem
                  name="Choice 4"
                  value="choice-4"
                  icon="iconoir-cancel"
                  :disabled="true"
                ></DropdownItem>
                <DropdownItem
                  name="Choice 5"
                  value="choice-5"
                  icon="iconoir-edit-pencil"
                  description="Lorem ipsum dolor sit amet, consectetur."
                ></DropdownItem>
                <DropdownItem
                  name="Choice 6"
                  value="choice-6"
                  icon="iconoir-edit-pencil"
                  description="Lorem ipsum dolor sit amet, consectetur."
                ></DropdownItem>
              </Dropdown>
            </div>
          </FormGroup>

          <FormGroup
            label="Very long dropdown"
            required
            class="margin-bottom-2"
          >
            <div style="width: 200px">
              <Dropdown v-model="longDropdown">
                <DropdownItem
                  :key="'some-2'"
                  :name="'Something'"
                  :value="'some-2'"
                ></DropdownItem>
                <DropdownItem
                  :key="'test-3'"
                  :name="'Test 3'"
                  :value="'test3'"
                ></DropdownItem>
                <DropdownItem
                  v-for="i in [
                    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
                  ]"
                  :key="i"
                  :name="'Choice ' + i"
                  :value="i"
                  :disabled="i === 7"
                ></DropdownItem>
                <DropdownItem
                  :key="'test-1'"
                  :name="'Test 1'"
                  :value="'test1'"
                ></DropdownItem>
                <DropdownItem
                  :key="'test-2'"
                  :name="'Test 2'"
                  :value="'test2'"
                ></DropdownItem>
              </Dropdown>
            </div>
          </FormGroup>

          <FormGroup
            label="Dropdown with footer"
            required
            class="margin-bottom-2"
          >
            <div style="width: 200px">
              <Dropdown v-model="dropdown" show-search show-footer>
                <DropdownItem name="Choice 1" value="choice-1"></DropdownItem>
                <DropdownItem
                  name="Choice 2"
                  value="choice-2"
                  icon="iconoir-edit-pencil"
                ></DropdownItem>
                <DropdownItem
                  name="Choice 3"
                  value="choice-3"
                  icon="iconoir-db"
                ></DropdownItem>
                <DropdownItem
                  name="Choice 4"
                  value="choice-4"
                  icon="iconoir-cancel"
                  :disabled="true"
                ></DropdownItem>
                <template #footer>
                  <a
                    class="select__footer-button"
                    @click="$refs.IntegrationCreateEditModal.show()"
                  >
                    <i class="iconoir-plus"></i>
                    Add item
                  </a>
                </template>
              </Dropdown>
            </div>
          </FormGroup>

          <FormGroup label="Dropdown by link" required class="margin-bottom-2">
            <div style="width: 200px">
              <a
                ref="dropdownLink"
                @click="$refs.dropdown1.toggle($refs.dropdownLink)"
                >Open dropdown</a
              >
              <Dropdown ref="dropdown1" v-model="dropdown" :show-input="false">
                <DropdownItem name="Choice 1" value="choice-1"></DropdownItem>
                <DropdownItem
                  name="Choice 2"
                  value="choice-2"
                  icon="iconoir-edit-pencil"
                ></DropdownItem>
                <DropdownItem
                  name="Choice 3"
                  value="choice-3"
                  icon="iconoir-db"
                ></DropdownItem>
                <DropdownItem
                  name="Choice 4"
                  value="choice-4"
                  icon="iconoir-cancel"
                  :disabled="true"
                ></DropdownItem>
              </Dropdown>
            </div>
          </FormGroup>

          <FormGroup label="Dropdown large" required class="margin-bottom-2">
            <div style="width: 200px">
              <Dropdown v-model="dropdown" :show-search="false" size="large">
                <DropdownItem name="Choice 1" value="choice-1"></DropdownItem>
                <DropdownItem
                  name="Choice 2"
                  value="choice-2"
                  icon="iconoir-edit-pencil"
                ></DropdownItem>
                <DropdownItem
                  name="Choice 3"
                  value="choice-3"
                  icon="iconoir-db"
                ></DropdownItem>
                <DropdownItem
                  name="Choice 4"
                  value="choice-4"
                  icon="iconoir-cancel"
                  :disabled="true"
                ></DropdownItem>
              </Dropdown>
            </div>
          </FormGroup>

          <FormGroup label="Dropdown error" required class="margin-bottom-2">
            <div style="width: 200px">
              <Dropdown v-model="dropdown" :error="true">
                <DropdownItem name="Choice 1" value="choice-1"></DropdownItem>
                <DropdownItem
                  name="Choice 2"
                  value="choice-2"
                  icon="iconoir-edit-pencil"
                  description="Lorem ipsum dolor sit amet, consectetur."
                ></DropdownItem>
                <DropdownItem
                  name="Choice 3"
                  value="choice-3"
                  icon="iconoir-db"
                ></DropdownItem>
                <DropdownItem
                  name="Choice 4"
                  value="choice-4"
                  icon="iconoir-cancel"
                  :disabled="true"
                ></DropdownItem>
                <DropdownItem
                  name="Choice 5"
                  value="choice-5"
                  icon="iconoir-edit-pencil"
                  description="Lorem ipsum dolor sit amet, consectetur."
                ></DropdownItem>
                <DropdownItem
                  name="Choice 6"
                  value="choice-6"
                  icon="iconoir-edit-pencil"
                  description="Lorem ipsum dolor sit amet, consectetur."
                ></DropdownItem>
              </Dropdown>
            </div>
          </FormGroup>

          <div class="control">
            <label class="control__label">Datepicker field</label>
            <div class="control__elements">
              value: {{ date }}
              <br />
              <br />
              <client-only>
                <date-picker
                  v-model="date"
                  :inline="true"
                  :monday-first="true"
                  class="datepicker"
                ></date-picker>
              </client-only>
            </div>
          </div>
        </div>
        <div class="margin-bottom-3">
          <Alert type="success" close-button>
            <template #title>Toast message</template>
            <p>
              Lorem ipsum dolor sit amet, <a href="#">consectetur</a> adipiscing
              elit. Sed quis gravida ante. Nulla nec elit dui. Nam nec dui
              ligula. Pellentesque feugiat erat vel porttitor euismod. Duis nec
              viverra urna. Praesent.
            </p>
            <template #actions>
              <button
                class="alert__actions-button-text alert__actions-button-text--normal"
              >
                Cancel
              </button>
              <button
                class="alert__actions-button-text alert__actions-button-text--loading"
              >
                Accept
              </button>
            </template>
          </Alert>

          <Alert type="warning" close-button>
            <template #title>Toast message</template>
            <p>
              Lorem ipsum dolor sit amet, <a href="#">consectetur</a> adipiscing
              elit. Sed quis gravida ante. Nulla nec elit dui. Nam nec dui
              ligula. Pellentesque feugiat erat vel porttitor euismod. Duis nec
              viverra urna. Praesent.
            </p>
            <template #actions>
              <button
                class="alert__actions-button-text alert__actions-button-text--normal"
              >
                Cancel
              </button>
              <button
                class="alert__actions-button-text alert__actions-button-text--loading"
              >
                Accept
              </button>
            </template>
          </Alert>

          <Alert type="info-primary" close-button>
            <template #title>Toast message</template>
            <p>
              Lorem ipsum dolor sit amet, <a href="#">consectetur</a> adipiscing
              elit. Sed quis gravida ante. Nulla nec elit dui. Nam nec dui
              ligula. Pellentesque feugiat erat vel porttitor euismod. Duis nec
              viverra urna. Praesent.
            </p>
            <template #actions>
              <Button type="primary" size="small"> Accept </Button>
              <button
                class="alert__actions-button-text alert__actions-button-text--normal"
              >
                Cancel
              </button>
            </template>
          </Alert>

          <Alert type="info-neutral" close-button>
            <template #title>Toast message</template>
            <p>
              Lorem ipsum dolor sit amet, <a href="#">consectetur</a> adipiscing
              elit. Sed quis gravida ante. Nulla nec elit dui. Nam nec dui
              ligula. Pellentesque feugiat erat vel porttitor euismod. Duis nec
              viverra urna. Praesent.
            </p>
            <template #actions>
              <button
                class="alert__actions-button-text alert__actions-button-text--normal"
              >
                Cancel
              </button>
              <button
                class="alert__actions-button-text alert__actions-button-text--loading"
              >
                Accept
              </button>
            </template>
          </Alert>

          <Alert type="danger" close-button>
            <template #title>Alert title</template>
            <template #actions>
              <button
                class="alert__actions-button-text alert__actions-button-text--normal alert__actions-button-text--loading"
              >
                Cancel
              </button>
            </template>
          </Alert>

          <Alert>
            <template #title>Alert title</template>
          </Alert>
        </div>
        <div
          class="margin-bottom-3 style-guide__buttons"
          :style="{ backgroundColor: 'white', padding: '5px' }"
        >
          <h3>Button</h3>

          <Button type="primary">Button primary</Button>
          <Button type="secondary">Button secondary</Button>
          <Button type="danger">Button danger</Button>
          <Button type="upload">Button upload</Button>
        </div>
        <div
          class="margin-bottom-3 style-guide__buttons"
          :style="{ backgroundColor: 'white', padding: '5px' }"
        >
          <h3>Button large</h3>

          <Button type="primary" size="large">Button primary</Button>
          <Button type="secondary" size="large">Button secondary</Button>
          <Button type="danger" size="large">Button danger</Button>
          <Button type="upload" size="large">Button upload</Button>
        </div>
        <div
          class="margin-bottom-3 style-guide__buttons"
          :style="{ backgroundColor: 'white', padding: '5px' }"
        >
          <h3>Button small</h3>

          <Button type="primary" size="small">Button primary</Button>
          <Button type="secondary" size="small">Button secondary</Button>
          <Button type="danger" size="small">Button danger</Button>
          <Button type="upload" size="small">Button upload</Button>
        </div>
        <div
          class="margin-bottom-3 style-guide__buttons"
          :style="{ backgroundColor: 'white', padding: '5px' }"
        >
          <h3>Button loading</h3>

          <Button type="primary" size="small" loading>Button primary</Button>
          <Button type="secondary" size="small" loading
            >Button secondary</Button
          >
          <Button type="danger" size="small" loading>Button danger</Button>
          <Button type="upload" size="small" loading>Button upload</Button>
        </div>
        <div
          class="margin-bottom-3 style-guide__buttons"
          :style="{ backgroundColor: 'white', padding: '5px' }"
        >
          <h3>Button disabled</h3>

          <Button type="primary" size="small" disabled>Button primary</Button>
          <Button type="secondary" size="small" disabled
            >Button secondary disabled</Button
          >
          <Button type="danger" size="small" disabled
            >Button danger disabled</Button
          >
        </div>

        <div
          class="margin-bottom-3 style-guide__buttons"
          :style="{ backgroundColor: 'white', padding: '5px' }"
        >
          <h3>Button with icon</h3>

          <Button type="primary" size="small" icon="iconoir-plus"
            >Button primary</Button
          >
          <Button type="secondary" size="small" icon="iconoir-plus"
            >Button secondary</Button
          >
          <Button type="danger" size="small" icon="iconoir-plus"
            >Button danger</Button
          >
        </div>

        <div
          class="margin-bottom-3"
          :style="{ backgroundColor: 'white', padding: '5px' }"
        >
          <h3>Button full width</h3>

          <Button
            class="margin-bottom-2"
            type="primary"
            icon="iconoir-plus"
            full-width
            >Button primary</Button
          >
          <Button
            class="margin-bottom-2"
            type="secondary"
            icon="iconoir-plus"
            full-width
            >Button secondary</Button
          >
          <Button
            class="margin-bottom-2"
            type="danger"
            icon="iconoir-plus"
            full-width
            >Button danger</Button
          >
        </div>

        <div
          class="margin-bottom-3"
          :style="{ backgroundColor: 'white', padding: '5px' }"
        >
          <h3>Button icon</h3>
          <div class="margin-bottom-2">
            Primary
            <ButtonIcon type="primary" icon="iconoir-basketball"></ButtonIcon>
          </div>

          <div>
            Secondary
            <ButtonIcon type="secondary" icon="iconoir-basketball"></ButtonIcon>
          </div>

          <ButtonIcon
            type="primary"
            icon="iconoir-basketball"
            loading
          ></ButtonIcon>

          <ButtonIcon
            type="primary"
            icon="iconoir-basketball"
            disabled
          ></ButtonIcon>
        </div>

        <div
          class="margin-bottom-3"
          :style="{ backgroundColor: 'white', padding: '5px' }"
        >
          <h3>Button text</h3>

          <ButtonText type="primary" icon="iconoir-plus"
            >Button text primary</ButtonText
          >

          <ButtonText type="secondary" icon="iconoir-plus"
            >Button text primary</ButtonText
          >

          <ButtonText type="primary" icon="iconoir-plus" loading
            >Button text loading</ButtonText
          >

          <ButtonText type="primary" icon="iconoir-plus" disabled
            >Button text disabled</ButtonText
          >
        </div>

        <div
          class="margin-bottom-3"
          :style="{ backgroundColor: 'white', padding: '5px' }"
        >
          <h3>Button add</h3>

          <ButtonAdd></ButtonAdd>

          <ButtonAdd disabled></ButtonAdd>
        </div>

        <div
          class="margin-bottom-3"
          style="background-color: #ffffff; padding: 20px"
        >
          <h3>Classic tabs</h3>
          <Tabs>
            <Tab :selected="true" :title="'Tab 1'">
              <p>
                Tab 1 content Lorem ipsum dolor sit amet,
                <a href="#">consectetur</a> adipiscing elit. Sed quis gravida
                ante. Nulla nec elit dui. Nam nec dui ligula. Pellentesque
                feugiat erat vel porttitor euismod. Duis nec viverra urna.
                Praesent.
              </p>
            </Tab>
            <Tab :title="'Tab 2'">
              <p>
                Tab 2 content Lorem ipsum dolor sit amet,
                <a href="#">consectetur</a> adipiscing elit. Sed quis gravida
                ante. Nulla nec elit dui. Nam nec dui ligula. Pellentesque
                feugiat erat vel porttitor euismod. Duis nec viverra urna.
                Praesent.
              </p>
            </Tab>
            <Tab :title="'Tab 3'">
              <p>
                Tab 3 content Lorem ipsum dolor sit amet,
                <a href="#">consectetur</a> adipiscing elit. Sed quis gravida
                ante. Nulla nec elit dui. Nam nec dui ligula. Pellentesque
                feugiat erat vel porttitor euismod. Duis nec viverra urna.
                Praesent.
              </p>
            </Tab>
          </Tabs>
        </div>

        <div class="margin-bottom-3">
          <div class="tooltip margin-bottom-2">
            <div class="tooltip__content">Example tooltip</div>
          </div>
          <div class="tooltip tooltip--top">
            <div class="tooltip__content">Tooltip top</div>
          </div>
        </div>
        <div class="margin-bottom-3 style-guide__contexts">
          <div class="context">
            <div class="context__menu-title">Vehicles</div>
            <ul class="context__menu">
              <li class="context__menu-item">
                <a class="context__menu-item-link" href="#">
                  <i class="context__menu-item-icon iconoir-edit-pencil"></i>
                  Rename database
                </a>
              </li>
              <li class="context__menu-item">
                <a class="context__menu-item-link" href="#">
                  <i class="context__menu-item-icon iconoir-bin"></i>
                  Delete table
                </a>
              </li>
              <li class="context__menu-item">
                <a
                  class="context__menu-item-link context__menu-item-link--loading"
                  href="#"
                >
                  <i class="context__menu-item-icon iconoir-bin"></i>
                  Loading
                </a>
              </li>
            </ul>
          </div>
          <div class="context" style="max-width: 264px">
            <div class="context__menu-title">Workspace permissions</div>
            <ul class="context__menu context__menu--can-be-active">
              <li class="context__menu-item">
                <a
                  href="#"
                  class="context__menu-item-link context__menu-item-link--with-desc active"
                >
                  <span class="context__menu-item-title">Admin</span>
                  <div class="context__menu-item-description">
                    Description of what an admin can or can’t do on the
                    workspace.
                  </div>
                  <i class="context__menu-active-icon iconoir-check"></i>
                </a>
              </li>
              <li class="context__menu-item">
                <a
                  href="#"
                  class="context__menu-item-link context__menu-item-link--with-desc disabled"
                >
                  <span class="context__menu-item-title">Admin</span>
                  <div class="context__menu-item-description">
                    Description of what an admin can or can’t do on the
                    workspace.
                  </div>
                </a>
              </li>
              <li class="context__menu-item">
                <a
                  href="#"
                  class="context__menu-item-link context__menu-item-link--with-desc context__menu-item-link--loading"
                >
                  <span class="context__menu-item-title">Builder</span>
                  <div class="context__menu-item-description">
                    Description of what a builder can or can’t do on the
                    workspace.
                  </div>
                </a>
              </li>
              <li class="context__menu-item context__menu-item--with-separator">
                <a
                  class="context__menu-item-link context__menu-item-link--delete"
                  href="#"
                >
                  Remove from workspace
                </a>
              </li>
            </ul>
          </div>
          <div class="select">
            <div class="select__search">
              <i class="select__search-icon iconoir-search"></i>
              <input
                type="text"
                class="select__search-input"
                placeholder="Search views"
              />
            </div>
            <ul v-auto-overflow-scroll class="select__items">
              <li class="select__item active">
                <a href="#" class="select__item-link">
                  <div class="select__item-name">Workspace name 1</div>
                </a>
                <i class="select__item-active-icon iconoir-check"></i>
                <a href="#" class="select__item-options">
                  <i class="baserow-icon-more-vertical"></i>
                </a>
              </li>
              <li class="select__item">
                <a href="#" class="select__item-link">
                  <div class="select__item-name">Workspace name 2</div>
                </a>
                <a href="#" class="select__item-options">
                  <i class="baserow-icon-more-vertical"></i>
                </a>
              </li>
              <li class="select__item select__item--loading">
                <a href="#" class="select__item-link">
                  <div class="select__item-name">Workspace name 3</div>
                </a>
                <a href="#" class="select__item-options">
                  <i class="baserow-icon-more-vertical"></i>
                </a>
              </li>
              <li class="select__item">
                <a href="#" class="select__item-link">
                  <div class="select__item-name">Workspace name 4</div>
                </a>
                <a href="#" class="select__item-options">
                  <i class="baserow-icon-more-vertical"></i>
                </a>
              </li>
            </ul>
            <div class="select__footer">
              <a href="#" class="select__footer-button">
                <i class="iconoir-plus"></i>
                Do something
              </a>
            </div>
          </div>
        </div>
        <div class="margin-bottom-3 style-guide__contexts">
          <div class="select">
            <div class="select__search">
              <i class="select__search-icon iconoir-search"></i>
              <input
                type="text"
                class="select__search-input"
                placeholder="Search views"
              />
            </div>
            <ul v-auto-overflow-scroll class="select__items">
              <li class="select__item">
                <a href="#" class="select__item-link">
                  <div class="select__item-name">
                    <i
                      class="select__item-icon iconoir-view-grid color-primary"
                    ></i>
                    Grid view name
                  </div>
                </a>
                <a
                  href="#"
                  class="select__item-options"
                  data-context=".context"
                >
                  <i class="baserow-icon-more-vertical"></i>
                </a>
              </li>
              <li class="select__item">
                <a href="#" class="select__item-link">
                  <div class="select__item-name">
                    <i
                      class="select__item-icon iconoir-view-grid color-primary"
                    ></i>
                    Grid view option 2.
                  </div>
                </a>
                <a href="#" class="select__item-options">
                  <i class="baserow-icon-more-vertical"></i>
                </a>
              </li>
              <li class="select__item">
                <a href="#" class="select__item-link">
                  <div class="select__item-name">
                    <i
                      class="select__item-icon iconoir-view-grid color-primary"
                    ></i>
                    Grid view 2
                  </div>
                </a>
                <a href="#" class="select__item-options">
                  <i class="baserow-icon-more-vertical"></i>
                </a>
              </li>
              <li class="select__item">
                <a href="#" class="select__item-link">
                  <div class="select__item-name">
                    <i
                      class="select__item-icon iconoir-view-grid color-primary"
                    ></i>
                    Grid view 3
                  </div>
                </a>
                <a href="#" class="select__item-options">
                  <i class="baserow-icon-more-vertical"></i>
                </a>
              </li>
            </ul>
            <div class="select__footer">
              <div class="select__footer-create">
                <a class="select__footer-create-link">
                  <i class="select__footer-create-icon iconoir-table"></i>
                  Grid
                  <i
                    class="select__footer-create-link-icon iconoir-plus"
                  ></i></a
                ><a class="select__footer-create-link">
                  <i class="select__footer-create-icon iconoir-view-grid"></i>
                  Gallery
                  <i
                    class="select__footer-create-link-icon iconoir-plus"
                  ></i></a
                ><a class="select__footer-create-link"
                  ><i class="select__footer-create-icon iconoir-edit"></i> Form
                  <i
                    class="select__footer-create-link-icon iconoir-plus"
                  ></i></a
                ><a class="select__footer-create-link"
                  ><i
                    class="select__footer-create-icon iconoir-kanban-board"
                  ></i>
                  Kanban
                  <i class="select__footer-create-link-icon iconoir-plus"></i>
                </a>
              </div>
            </div>
          </div>
          <div class="context datepicker-context">
            <client-only>
              <date-picker
                v-model="date"
                :inline="true"
                :monday-first="true"
                class="datepicker"
              ></date-picker>
            </client-only>
          </div>
          <div class="time-select">
            <ul>
              <li>
                <a href="#">00:00</a>
              </li>
              <li>
                <a href="#">00:30</a>
              </li>
              <li>
                <a href="#" class="active">01:00</a>
              </li>
              <li>
                <a href="#">01:30</a>
              </li>
              <li>
                <a href="#">02:00</a>
              </li>
              <li>
                <a href="#">02:30</a>
              </li>
              <li>
                <a href="#">03:00</a>
              </li>
              <li>
                <a href="#">03:30</a>
              </li>
            </ul>
          </div>
        </div>
        <div class="formula-field margin-bottom-3">
          <div class="formula-field__input">
            <FormTextarea
              v-model="formula"
              auto-expandable
              class="auto-expandable-textarea--input-formula"
            ></FormTextarea>
          </div>
          <div class="formula-field__body">
            <div class="formula-field__items">
              <ul class="formula-field__item-group">
                <li class="formula-field__item-group-title">Fields</li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="iconoir-text formula-field__item-icon" />
                    Text
                  </a>
                </li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="baserow-icon-hashtag formula-field__item-icon" />
                    Number
                  </a>
                </li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="iconoir-check formula-field__item-icon" />
                    Checkbox
                  </a>
                </li>
              </ul>
              <ul class="formula-field__item-group">
                <li class="formula-field__item-group-title">Constants</li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="baserow-icon-hashtag formula-field__item-icon" />
                    e
                  </a>
                </li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="baserow-icon-hashtag formula-field__item-icon" />
                    pi
                  </a>
                </li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="iconoir-check formula-field__item-icon" />
                    true
                  </a>
                </li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="iconoir-check formula-field__item-icon" />
                    false
                  </a>
                </li>
              </ul>
              <ul class="formula-field__item-group">
                <li class="formula-field__item-group-title">Operators</li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="iconoir-text formula-field__item-icon" />
                    If
                  </a>
                </li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="baserow-icon-hashtag formula-field__item-icon" />
                    add
                  </a>
                </li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="baserow-icon-hashtag formula-field__item-icon" />
                    subtract
                  </a>
                </li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="baserow-icon-hashtag formula-field__item-icon" />
                    multiply
                  </a>
                </li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="baserow-icon-hashtag formula-field__item-icon" />
                    divide
                  </a>
                </li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="baserow-icon-hashtag formula-field__item-icon" />
                    pow
                  </a>
                </li>
              </ul>
              <ul class="formula-field__item-group">
                <li class="formula-field__item-group-title">Functions</li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="iconoir-text formula-field__item-icon" />
                    concat
                  </a>
                </li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="iconoir-text formula-field__item-icon" />
                    join
                  </a>
                </li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="iconoir-text formula-field__item-icon" />
                    slice
                  </a>
                </li>
                <li class="formula-field__item">
                  <a href="#" class="formula-field__item-link">
                    <i class="baserow-icon-hashtag formula-field__item-icon" />
                    length
                  </a>
                </li>
              </ul>
            </div>
            <div class="formula-field__description">
              <div class="formula-field__description-heading-1">concat</div>
              <div class="formula-field__description-text">
                Concatenates its arguments and returns the result.
              </div>
              <div class="formula-field__description-heading-2">Syntax</div>
              <pre
                class="formula-field__description-example"
              ><code>concat(text...)</code></pre>
              <div class="formula-field__description-heading-2">Examples</div>
              <pre
                class="formula-field__description-example"
              ><code>concat(“Hello”, “World”) == “HelloWorld”
“Hello” + “World” == “HelloWorld”</code></pre>
            </div>
          </div>
        </div>
        <div class="margin-bottom-3">
          <Button
            append-icon="iconoir-edit-pencil"
            @click="$refs.context1.toggle($event.target)"
          >
            Toggle context
          </Button>
          <Context ref="context1">
            <div class="context__menu-title">Vehicles</div>
            <ul class="context__menu">
              <li class="context__menu-item">
                <a class="context__menu-item-link" href="#">
                  <i class="context__menu-item-icon iconoir-edit-pencil"></i>
                  This does nothing
                </a>
              </li>
              <li class="context__menu-item">
                <a
                  class="context__menu-item-link"
                  @click="$refs.context2.toggle($event.target)"
                >
                  Open another context
                </a>
                <Context ref="context2">
                  <div class="context__menu-title">Open modal</div>
                  <ul class="context__menu">
                    <li class="context__menu-item">
                      <a
                        class="context__menu-item-link"
                        @click="$refs.modal1.show()"
                      >
                        <i
                          class="context__menu-item-icon iconoir-edit-pencil"
                        ></i>
                        Click to open modal
                      </a>
                    </li>
                    <Modal ref="modal1">
                      <h2 class="box__title">Modal inside a context</h2>
                      <Button
                        icon="iconoir-edit-pencil"
                        @click="$refs.context3.toggle($event.target)"
                        >Toggle context</Button
                      >
                      <Context ref="context3">
                        <div class="context__menu-title">Vehicles</div>
                        <ul class="context__menu">
                          <li class="context__menu-item">
                            <a class="context__menu-item-link" href="#">
                              <i
                                class="context__menu-item-icon iconoir-edit-pencil"
                              ></i>
                              This does nothing
                            </a>
                          </li>
                          <li class="context__menu-item">
                            <a
                              class="context__menu-item-link"
                              @click="$refs.context4.toggle($event.target)"
                            >
                              Open another context
                            </a>
                            <Context ref="context4">
                              <div class="context__menu-title">End!</div>
                            </Context>
                          </li>
                          <li class="context__menu-item">
                            <a class="context__menu-item-link" href="#">
                              <i
                                class="context__menu-item-icon iconoir-bin"
                              ></i>
                              This does nothing
                            </a>
                          </li>
                        </ul>
                      </Context>
                    </Modal>
                  </ul>
                </Context>
              </li>
              <li>
                <a href="#">
                  <i class="context__menu-item-icon iconoir-bin"></i>
                  This does nothing
                </a>
              </li>
            </ul>
          </Context>
          <Button @click="$refs.modal2.show()">show modal</Button>
          <Modal ref="modal2">
            <h2 class="box__title">An example modal</h2>
            <p>
              Mauris dignissim massa ac justo consequat porttitor. Lorem ipsum
              dolor sit amet, consectetur adipiscing elit. Mauris vel tellus
              suscipit, gravida libero a, egestas urna. Quisque tellus nisi,
              consequat et interdum non, posuere sed lacus. Morbi fermentum
              lorem sed vestibulum tristique. Vivamus scelerisque molestie
              ligula vel elementum. Etiam metus lacus, commodo sit amet
              tristique luctus, pulvinar eget justo. Fusce sed vehicula dolor.
              Aliquam sollicitudin fringilla augue, posuere maximus orci
              sollicitudin a. Vestibulum egestas tristique nunc, tristique
              dignissim mauris dictum imperdiet. Mauris ultrices ac eros at
              fringilla. Praesent ut tincidunt dui.
            </p>
          </Modal>
          <Button
            @click="
              $store.dispatch('toast/success', {
                title: 'Custom success toast',
                message: 'Mauris dignissim massa ac justo consequat porttitor.',
              })
            "
          >
            toggle success toast
          </Button>
          <Button
            type="danger"
            @click="
              $store.dispatch('toast/error', {
                title: 'Custom error toast',
                message: 'Mauris dignissim massa ac justo consequat porttitor.',
              })
            "
          >
            toggle error toast
          </Button>
          <Button
            type="danger"
            @click="
              $store.dispatch('toast/warning', {
                title: 'Custom warning toast',
                message: 'Mauris dignissim massa ac justo consequat porttitor.',
              })
            "
          >
            toggle warning toast
          </Button>
          <Button
            @click="
              $store.dispatch('toast/info', {
                title: 'Custom info toast',
                message: 'Mauris dignissim massa ac justo consequat porttitor.',
              })
            "
          >
            toggle info toast
          </Button>
        </div>
        <div class="margin-bottom-3">
          <div class="modal__box">
            <div class="modal__actions">
              <a class="modal__close">
                <i class="iconoir-cancel"></i>
              </a>
            </div>
            <h2 class="box__title">An example modal</h2>
            <p>
              Mauris dignissim massa ac justo consequat porttitor. Lorem ipsum
              dolor sit amet, consectetur adipiscing elit. Mauris vel tellus
              suscipit, gravida libero a, egestas urna. Quisque tellus nisi,
              consequat et interdum non, posuere sed lacus. Morbi fermentum
              lorem sed vestibulum tristique. Vivamus scelerisque molestie
              ligula vel elementum. Etiam metus lacus, commodo sit amet
              tristique luctus, pulvinar eget justo. Fusce sed vehicula dolor.
              Aliquam sollicitudin fringilla augue, posuere maximus orci
              sollicitudin a. Vestibulum egestas tristique nunc, tristique
              dignissim mauris dictum imperdiet. Mauris ultrices ac eros at
              fringilla. Praesent ut tincidunt dui.
            </p>
            <div class="delete-section">
              <div class="delete-section__label">
                <div class="delete-section__label-icon">
                  <i class="iconoir-warning-triangle"></i>
                </div>
                Will also be permanently deleted
              </div>
              <p class="delete-section__description">
                Mauris dignissim massa ac justo consequat porttitor. Lorem ipsum
                dolor sit amet, consectetur adipiscing elit. Mauris vel tellus
                suscipit, gravida libero a, egestas urna. Quisque tellus nisi,
                consequat et interdum non, posuere sed lacus.
              </p>
              <ul class="delete-section__list">
                <li>
                  <i class="delete-section__list-icon iconoir-db"></i>
                  Vehicles
                  <small>including 12 tables</small>
                </li>
                <li>
                  <i class="delete-section__list-icon iconoir-db"></i>
                  Webshop
                  <small>including 12 tables</small>
                </li>
              </ul>
            </div>
            <div class="actions actions--right">
              <Button size="large" overflow>Validate</Button>
            </div>
          </div>
          <div class="modal__box modal__box--with-sidebar">
            <div class="modal__actions">
              <a class="modal__close">
                <i class="iconoir-cancel"></i>
              </a>
            </div>
            <div
              class="modal__box-sidebar modal__box-sidebar--left modal__box-sidebar--scrollable"
            >
              <div class="modal-sidebar__head">
                <div class="modal-sidebar__head-initials-icon">B</div>
                <div class="modal-sidebar__head-name">Settings</div>
              </div>
              <ul class="modal-sidebar__nav">
                <li>
                  <a class="modal-sidebar__nav-link active"
                    ><i class="modal-sidebar__nav-icon iconoir-user"></i>
                    Account
                  </a>
                </li>
                <li>
                  <a class="modal-sidebar__nav-link"
                    ><i class="modal-sidebar__nav-icon iconoir-lock"></i>
                    Password
                  </a>
                </li>
                <li>
                  <a class="modal-sidebar__nav-link"
                    ><i class="modal-sidebar__nav-icon iconoir-key-alt"></i>
                    API Tokens
                  </a>
                </li>
                <li>
                  <a class="modal-sidebar__nav-link"
                    ><i class="modal-sidebar__nav-icon iconoir-eye-off"></i>
                    Delete account
                  </a>
                </li>
              </ul>
            </div>
            <div class="modal__box-content">
              <h2 class="box__title">An example modal</h2>
              <p>
                Mauris dignissim massa ac justo consequat porttitor. Lorem ipsum
                dolor sit amet, consectetur adipiscing elit. Mauris vel tellus
                suscipit, gravida libero a, egestas urna. Quisque tellus nisi,
                consequat et interdum non, posuere sed lacus. Morbi fermentum
                lorem sed vestibulum tristique. Vivamus scelerisque molestie
                ligula vel elementum. Etiam metus lacus, commodo sit amet
                tristique luctus, pulvinar eget justo. Fusce sed vehicula dolor.
                Aliquam sollicitudin fringilla augue, posuere maximus orci
                sollicitudin a. Vestibulum egestas tristique nunc, tristique
                dignissim mauris dictum imperdiet. Mauris ultrices ac eros at
                fringilla. Praesent ut tincidunt dui.
              </p>
            </div>
          </div>
        </div>
        <div class="margin-bottom-3">
          <div class="card" style="width: 320px">
            <div class="card__cover">
              <i class="card__cover-empty-image iconoir-media-image"></i>
              <div
                v-if="false"
                class="card__cover-image"
                :style="{
                  'background-image':
                    'url(https://www.w3schools.com/cssref/mountain.jpg)',
                }"
              ></div>
            </div>
            <div class="card__fields">
              <div class="card__field">
                <div class="card__field-name">Text</div>
                <div class="card__field-value">
                  <div class="card-text">This is a single line text field</div>
                </div>
              </div>
              <div class="card__field">
                <div class="card__field-name">Long text</div>
                <div class="card__field-value">
                  <div class="card-text">
                    This is a long text field with a very long content that
                    doesn't fit.
                  </div>
                </div>
              </div>
              <div class="card__field">
                <div class="card__field-name">Link row</div>
                <div class="card__field-value">
                  <div class="card-many-to-many__list-wrapper">
                    <div class="card-many-to-many__list">
                      <div class="card-many-to-many__item card-link-row">
                        <span class="card-many-to-many__name">
                          Value 1 with a very long name that doesn't
                        </span>
                      </div>
                      <div
                        class="card-many-to-many__item card-link-row card-link-row--unnamed"
                      >
                        <span class="card-many-to-many__name">
                          unnamed row 1
                        </span>
                      </div>
                      <div class="card-many-to-many__item card-link-row">
                        <span class="card-many-to-many__name">
                          Another value
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div class="card__field">
                <div class="card__field-name">Number</div>
                <div class="card__field-value">
                  <div class="card-text">205</div>
                </div>
              </div>
              <div class="card__field">
                <div class="card__field-name">Decimal</div>
                <div class="card__field-value">
                  <div class="card-text">205.55</div>
                </div>
              </div>
              <div class="card__field">
                <div class="card__field-name">Boolean</div>
                <div class="card__field-value">
                  <div class="card-boolean">
                    <i class="iconoir-check"></i>
                  </div>
                </div>
              </div>
              <div class="card__field">
                <div class="card__field-name">Date</div>
                <div class="card__field-value">
                  <div class="card-text">2021-01-01</div>
                </div>
              </div>
              <div class="card__field">
                <div class="card__field-name">Datetime</div>
                <div class="card__field-value">
                  <div class="card-text">2021-01-01</div>
                </div>
              </div>
              <div class="card__field">
                <div class="card__field-name">URL</div>
                <div class="card__field-value">
                  <div class="card-text">
                    <a href="#">http://baserow.io</a>
                  </div>
                </div>
              </div>
              <div class="card__field">
                <div class="card__field-name">Email</div>
                <div class="card__field-value">
                  <div class="card-text">
                    <a href="#">bram@baserow.io</a>
                  </div>
                </div>
              </div>
              <div class="card__field">
                <div class="card__field-name">File</div>
                <div class="card__field-value">
                  <div class="card-file__list-wrapper">
                    <ul class="card-file__list">
                      <li class="card-file__item">
                        <img
                          src="http://localhost:4000/media/thumbnails/tiny/NcTfu10MwH9xtUkzL5jcmqIDXE0vkHin_1e01581444c66c952aa585f6fc79a671885b75053d275329f20e7b5faa73d7ec.png"
                          class="card-file__image"
                        />
                      </li>
                      <li class="card-file__item">
                        <img
                          src="http://localhost:4000/media/thumbnails/tiny/E413HC1eHsw9gakeRrpUOodHprEBT1pv_01bb5d9bbbd9addb39d1352877ca061573f2ca8ba64631ae5d4b7f8e16f6b18b.png"
                          class="card-file__image"
                        />
                      </li>
                      <li class="card-file__item">
                        <i class="card-file__icon iconoir-page-empty"></i>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
              <div class="card__field">
                <div class="card__field-name">Single select</div>
                <div class="card__field-value">
                  <div
                    class="card-single-select-option background-color--orange"
                  >
                    Option 1 with a very long name that doesn't fit
                    unfortunately.
                  </div>
                </div>
              </div>
              <div class="card__field">
                <div class="card__field-name">Single select</div>
                <div class="card__field-value">
                  <div class="card-single-select-option background-color--gray">
                    Option 2
                  </div>
                </div>
              </div>
              <div class="card__field">
                <div class="card__field-name">Multiple select</div>
                <div class="card__field-value">
                  <div class="card-many-to-many__list-wrapper">
                    <div class="card-many-to-many__list">
                      <div
                        class="card-many-to-many__item card-multiple-select-option background-color--green"
                      >
                        <span class="card-many-to-many__name">
                          Option value 1
                        </span>
                      </div>
                      <div
                        class="card-many-to-many__item card-multiple-select-option background-color--blue"
                      >
                        <span class="card-many-to-many__name">
                          Option 2 with a very long name that doesn't fit
                        </span>
                      </div>
                      <div
                        class="card-many-to-many__item card-multiple-select-option background-color--blue"
                      >
                        <span class="card-many-to-many__name"> Option 3 </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div class="card__field">
                <div class="card__field-name">Phone</div>
                <div class="card__field-value">
                  <div class="card-text">
                    <a href="#">+316 12345678</a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div
          class="margin-bottom-3"
          style="background-color: #ffffff; position: relative; height: 1000px"
        >
          <div class="data-table">
            <div class="data-table__header">
              <h1 class="data-table__title">12 Members in ACME Corp</h1>
              <div class="data-table__actions">
                <FormInput
                  left-icon="iconoir-search"
                  placeholder="Find member..."
                ></FormInput>
                <Button href="#" size="large" class="margin-left-2">
                  Invite member
                </Button>
              </div>
            </div>
            <div class="data-table__body">
              <table class="data-table__table">
                <thead>
                  <tr class="data-table__table-row">
                    <th
                      class="data-table__table-cell data-table__table-cell--sticky-left data-table__table-cell--header"
                    >
                      <div class="data-table__table-cell-head">
                        <Checkbox v-model="checkbox"></Checkbox>
                      </div>
                    </th>
                    <th
                      class="data-table__table-cell data-table__table-cell--header"
                    >
                      <div class="data-table__table-cell-head">
                        <a href="#" class="data-table__table-cell-head-link"
                          >Name</a
                        >
                        <div>
                          <i class="iconoir-sort-down"></i>
                          0
                        </div>
                      </div>
                    </th>
                    <th
                      class="data-table__table-cell data-table__table-cell--header"
                    >
                      <div class="data-table__table-cell-head">Email</div>
                    </th>
                    <th
                      class="data-table__table-cell data-table__table-cell--header"
                    >
                      <div class="data-table__table-cell-head">
                        Workspace permissions
                        <div>
                          <i class="iconoir-sort-up"></i>
                          1
                        </div>
                      </div>
                    </th>
                    <th
                      class="data-table__table-cell data-table__table-cell--header"
                    >
                      <div class="data-table__table-cell-head">Team</div>
                    </th>
                    <th
                      class="data-table__table-cell data-table__table-cell--header data-table__table-cell--sticky-right"
                    >
                      <div class="data-table__table-cell-head"></div>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(i, i2) in new Array(10)"
                    :key="i2"
                    class="data-table__table-row"
                    :class="{
                      'data-table__table-row--selected': i2 === 2,
                      'data-table__table-row--hover': i2 === 4,
                    }"
                  >
                    <td
                      class="data-table__table-cell data-table__table-cell--sticky-left"
                    >
                      <div class="data-table__table-cell-content">
                        <Checkbox v-model="checkbox"></Checkbox>
                      </div>
                    </td>
                    <td class="data-table__table-cell">
                      <div class="data-table__table-cell-content">
                        This is a very long name that doesn't completely fit.
                      </div>
                    </td>
                    <td class="data-table__table-cell">
                      <div class="data-table__table-cell-content">
                        This is a very long name that doesn't completely fit.
                      </div>
                    </td>
                    <td class="data-table__table-cell">
                      <div class="data-table__table-cell-content">
                        This is a very long name that doesn't completely fit.
                      </div>
                    </td>
                    <td class="data-table__table-cell">
                      <div class="data-table__table-cell-content">
                        This is a very long name that doesn't completely fit.
                      </div>
                    </td>
                    <td
                      class="data-table__table-cell data-table__table-cell--sticky-right"
                    >
                      <div class="data-table__table-cell-content">
                        <div class="data-table__more-wrapper">
                          <a href="#" class="data-table__more">
                            <i
                              class="data-table__more-icon baserow-icon-more-horizontal"
                            ></i>
                          </a>
                        </div>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="data-table__footer">
              <Paginator :page="1" :total-pages="10"></Paginator>
            </div>
          </div>
        </div>
        <div class="margin-bottom-3" style="background-color: #ffffff">
          <h2>List component</h2>
          <List
            :items="[
              { id: 1, name: 'test', image: image },
              { id: 2, name: 'test2', image: image },
              { id: 2, name: 'test3', image: image },
              { id: 2, name: 'test4', image: image },
            ]"
            :attributes="['name']"
          >
            <template #left-side="{ item }">
              <img :src="item.image" />
            </template>
            <template #right-side="{ item }">
              <div>
                <Button
                  size="tiny"
                  icon="edit"
                  @click="alert('should edit item ' + item.name)"
                />
                <Button
                  size="tiny"
                  icon="iconoir-bin"
                  @click="alert('should delete item ' + item.name)"
                />
              </div>
            </template>
          </List>
        </div>

        <div class="margin-bottom-3">
          <h2>Avatars</h2>
          <div style="display: flex; gap: 10px; padding: 0.5em">
            <Avatar size="small" icon="iconoir-bin" />
            <Avatar size="small" icon="iconoir-bin" color="yellow" />
            <Avatar size="small" icon="iconoir-bin" color="red" />
            <Avatar size="small" icon="iconoir-bin" color="transparent" />
            <Avatar size="small" :image="image" />
            <Avatar size="small" initials="BW" color="neutral" />
            <Avatar size="small" initials="BW" color="cyan" rounded />
            <Avatar size="small" icon="iconoir-bin" />
            <Avatar size="small" :image="image" color="neutral" />
            <Avatar size="small" initials="BW" color="red" :rounded="false" />
          </div>
          <div style="display: flex; gap: 10px; padding: 0.5em">
            <Avatar size="medium" icon="iconoir-bin" />
            <Avatar size="medium" icon="iconoir-bin" color="yellow" />
            <Avatar size="medium" icon="iconoir-bin" color="red" />
            <Avatar size="medium" icon="iconoir-bin" color="transparent" />
            <Avatar size="medium" :image="image" />
            <Avatar size="medium" initials="BW" color="neutral" />
            <Avatar size="medium" initials="BW" color="cyan" rounded />
            <Avatar size="medium" icon="iconoir-bin" />
            <Avatar size="medium" :image="image" color="neutral" />
            <Avatar size="medium" initials="BW" color="red" />
          </div>
          <div style="display: flex; gap: 10px; padding: 0.5em">
            <Avatar size="large" icon="iconoir-bin" />
            <Avatar size="large" icon="iconoir-bin" color="yellow" />
            <Avatar size="large" icon="iconoir-bin" color="red" />
            <Avatar size="large" icon="iconoir-bin" color="transparent" />
            <Avatar size="large" :image="image" />
            <Avatar size="large" initials="BW" color="neutral" />
            <Avatar size="large" initials="BW" color="cyan" rounded />
            <Avatar size="large" icon="iconoir-bin" />
            <Avatar size="large" :image="image" color="neutral" />
            <Avatar size="large" initials="BW" color="red" />
          </div>

          <div style="display: flex; gap: 10px; padding: 0.5em">
            <Avatar size="x-large" icon="iconoir-bin" />
            <Avatar size="x-large" icon="iconoir-bin" color="yellow" />
            <Avatar size="x-large" icon="iconoir-bin" color="red" />
            <Avatar size="x-large" icon="iconoir-bin" color="transparent" />
            <Avatar size="x-large" :image="image" />
            <Avatar size="x-large" initials="BW" color="neutral" />
            <Avatar size="x-large" initials="BW" color="cyan" rounded />
            <Avatar size="x-large" icon="iconoir-bin" />
            <Avatar size="x-large" :image="image" />
            <Avatar size="x-large" initials="BW" color="red" />
          </div>
        </div>
        <div class="margin-bottom-3">
          <h2>Presentations</h2>
          <Presentation
            title="My baserow integration"
            subtitle="Local baserow integration"
            class="margin-bottom-2"
          />
          <Presentation
            title="My baserow integration"
            subtitle="Local baserow integration"
            initials="LB"
            class="margin-bottom-2"
          />
          <Presentation
            title="My baserow integration"
            subtitle="Local baserow integration"
            icon="iconoir-db"
            class="margin-bottom-2"
          />
          <Presentation
            :image="image"
            title="My baserow integration"
            subtitle="Local baserow integration"
            avatar-color="neutral"
            class="margin-bottom-2"
          />
          <Presentation
            :image="image"
            title="My baserow integration"
            subtitle="Local baserow integration with a very long description"
            avatar-color="neutral"
            class="margin-bottom-2"
          />
        </div>
        <div
          id="colorPicker"
          class="margin-bottom-3"
          style="background-color: #ffffff; padding: 20px"
        >
          <ColorPicker ref="colorPicker" v-model="color"></ColorPicker>
          <br /><br />
          <a
            ref="colorPickerLink"
            @click="$refs.colorPicker.toggle($refs.colorPickerLink)"
          >
            Open color picker context
          </a>
          <ColorPickerContext
            ref="colorPicker"
            v-model="color"
            :variables="colorVariables"
          ></ColorPickerContext>
          <br /><br />
          {{ color }} - {{ resolveColor(color, colorVariables) }} <br /><br />
          <br />
          <ColorInput v-model="color" :color-variables="colorVariables" />
          <ColorInput
            v-model="color"
            :color-variables="colorVariables"
            :allow-opacity="false"
          />
        </div>

        <div class="margin-bottom-3">
          <h2>Call to action</h2>
          <CallToAction> My call to action. Click me! </CallToAction>
          <br />
          <CallToAction icon="baserow-icon-plus">
            Call to action with an icon
          </CallToAction>
        </div>
        <br /><br /><br />
        <br /><br /><br />
        <br /><br /><br />
      </div>
    </div>
  </div>
</template>

<script>
import Toasts from '@baserow/modules/core/components/toasts/Toasts'
import BaserowIcon from '@baserow/modules/core/static/img/logoOnly.svg'
import ColorPickerContext from '@baserow/modules/core/components/ColorPickerContext.vue'
import ColorPicker from '@baserow/modules/core/components/ColorPicker.vue'
import Paginator from '@baserow/modules/core/components/Paginator.vue'
import { resolveColor } from '@baserow/modules/core/utils/colors'

export default {
  components: {
    ColorPicker,
    ColorPickerContext,
    Toasts,
    Paginator,
  },
  data() {
    return {
      checkbox: false,
      radio: 'a',
      radioButton: 'a',
      switchValue: false,
      switchUnknown: 2,
      dropdown: '',
      dropdownMultiple: [],
      longDropdown: '0',
      date: '',
      formula: 'concat(field("Text"), field("Text"))',
      image: BaserowIcon,
      input: '',
      color: 'primary',
      colorVariables: [
        { name: 'Primary', value: 'primary', color: '#985353ff' },
        { name: 'Secondary', value: 'secondary', color: '#545398ff' },
      ],
      radioOptions: [
        { value: 'a', label: 'Option A' },
        { value: 'b', label: 'Option B' },
        { value: 'c', label: 'Option C' },
        { value: 'd', label: 'Option D', loading: true },
        { value: 'e', label: 'Option D', disabled: true },
      ],
      radioOptionIcons: [
        { value: 'a', icon: 'iconoir-align-left' },
        { value: 'a', icon: 'iconoir-align-center' },
        { value: 'a', icon: 'iconoir-align-right' },
      ],
    }
  },
  head() {
    return {
      title: 'Style guide',
    }
  },
  methods: {
    resolveColor,
    alert(message) {
      alert(message)
    },
  },
}
</script>
