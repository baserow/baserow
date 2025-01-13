# Loading animations

When an async operations happens, we always want to inform the user that something is
happening. Without a loading animation, it can feel like nothing is happening, and the
users easily think the application is slow.

## Spinner

**Spinner**: There are various build-in ways of showing a loading animation. One is a
simple spinner that's rendered in the page flow.

```vue
<div class="loading"></div>
```

**Loading overlay**: The loading overlay is positioned absolute and takes the same width
and height as the relative parent. There is a gray transparent background, and it
renders a loading spinner in the center.

```vue
<div class="width: 200px; height; 200px; position: relative;">
  <div class="loading-overlay"></div>
</div>
```

**Loading absolute center**: The loading absolute center renders a loading spinner in
the center of the relative parent.

```vue
<div class="width: 200px; height; 200px; position: relative;">
  <div class="loading-absolute-center"></div>
</div>
```

**Button**: If the action is initiated by clicking on a button, we typically put the
button in a loading state until it completes. The width of the button doesn't change
during loading.

```vue
<Button type="primary" :disabled="true" :loading="true">
  click
</Button>
```

## Loading animation per operation

- Submitting a form: **Button**
- Clicking a button: *Button**
- Opening a modal that needs to fetch some resources: **Spinner**
- Fixed height container: **Loading overlay** or **Loading absolute center**

## Example

```vue
<template>
  <div>
    <Button
      type="primary"
      :loading="loading"
      :disabled="loading"
      @click="save"
    >Click to save</Button>
  </div>
</template>

<script>
export default {
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async save() {
      this.loading = true
        
      try {
        await TestService(this.$client).save()
      } catch (error) {
        notifyIf(error)
      } finally {
        this.loading = false
      }
    }
  }
}
</script>
```

## Testing

When testing any async operations, like making an AJAX request, make sure to test
by slowing down the operation. This can for example be done by faking a slow  internet
connection to make sure that a loading is visible while executing.

### Firefox

Open the developer console, click on the "Networking" tab, and change the
"No throttling" dropdown on the right to "GPRS". Now run the operation, and check if
the loading animation is working as expected.

### Chrome

Open the developer console, click on the "Networking" tab, and change the
"No throttling" dropdown in the middle to "3G". Now run the operation, and check if the
loading animation is working as expected.
