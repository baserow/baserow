import UserFileService from '@baserow/modules/core/services/userFile'

/**
 * This directive can be used to enable drag and drop (or click) user file upload.
 * The selected files will be uploaded as a user file and the response, containing
 * the file name, url, thumbnails etc will be communicated via the `done` function.
 * The dragging and uploading state is communicated by calling the provided functions.
 * It is possible for users to drag and drop a file inside the element. Clicking on the
 * element opens a file picker.
 *
 * Example:
 * <div
 *   v-user-file-upload="{
 *     check: (file) => {
 *        // Check if the file is accepted.
 *        return true
 *      },
 *      enter: () => {
 *        // Entered dragging state.
 *      },
 *      leave: () => {
 *        // Leaving dragging state.
 *      },
 *      progress: (event) => {
 *        // Upload progress changes.
 *        const percentage = Math.round((event.loaded * 100) / event.total)
 *        console.log(percentage)
 *      },
 *      done: (file) => {
 *        // The file has been uploaded.
 *        console.log(file)
 *      },
 *   }"
 * >
 *   Drop here
 * </div>
 */
export default {
  /**
   * Registers all the needed drop, drag and click events needed.
   */
  beforeMount(el, binding, vnode) {
    binding.dir.updated(el, binding)

    // The input that is needed to open the file chooser.
    el.userFileUploadElement = document.createElement('input')
    el.userFileUploadElement.accept = el.userFileUploadValue.accept()
    el.userFileUploadElement.type = 'file'
    el.userFileUploadElement.style.display = 'none'
    el.userFileUploadElement.addEventListener('change', (event) => {
      binding.dir.upload(el, event, binding.instance.$client)
    })

    // The counter that is used to calculate if the user is dragging a file over the
    // drop zone. It could be that enter and leave event are going are called
    // multiple times without reentering the drop zone.
    el.userFileUploadDragCounter = 0

    el.userFileUploadDrop = (event) => {
      event.preventDefault()
      binding.dir.upload(el, event, binding.instance.$client)
    }
    el.addEventListener('drop', el.userFileUploadDrop)

    el.userFileUploadDragOver = (event) => {
      event.preventDefault()
    }
    el.addEventListener('dragover', el.userFileUploadDragOver)

    el.userFileUploadDragEnter = (event) => {
      event.preventDefault()
      if (el.userFileUploadDragCounter === 0) {
        el.userFileUploadValue.enter()
      }
      el.userFileUploadDragCounter++
    }
    el.addEventListener('dragenter', el.userFileUploadDragEnter)

    el.userFileUploadDragLeave = () => {
      el.userFileUploadDragCounter--
      if (el.userFileUploadDragCounter === 0) {
        el.userFileUploadValue.leave()
      }
    }
    el.addEventListener('dragleave', el.userFileUploadDragLeave)

    el.userFileUploadClick = (event) => {
      event.preventDefault()
      el.userFileUploadElement.click(event)
    }
    el.addEventListener('click', el.userFileUploadClick)
  },
  /**
   * Removes all the events registered in the bind function.
   */
  unmounted(el) {
    el.removeEventListener('drop', el.userFileUploadDrop)
    el.removeEventListener('dragover', el.userFileUploadDragOver)
    el.removeEventListener('dragenter', el.userFileUploadDragEnter)
    el.removeEventListener('dragleave', el.userFileUploadDragLeave)
    el.removeEventListener('click', el.userFileUploadClick)
  },
  updated(el, binding) {
    const defaults = {
      accept() {
        return '*'
      },
      check() {
        return true
      },
      enter() {},
      leave() {},
      progress() {},
      done() {},
      error() {},
    }
    el.userFileUploadValue = Object.assign(defaults, binding.value)
  },
  /**
   * Called when a file must be uploaded. The progress will be shared by calling the
   * provided functions.
   */
  async upload(el, event, client) {
    const files = event.target.files
      ? event.target.files
      : event.dataTransfer.files

    if (
      files === null ||
      files.length === 0 ||
      !el.userFileUploadValue.check(files[0])
    ) {
      return
    }

    try {
      const { data } = await UserFileService(client).uploadFile(
        files[0],
        el.userFileUploadValue.progress
      )

      el.userFileUploadValue.done(data)
    } catch (e) {
      el.userFileUploadValue.error(e)
    }
  },
}
