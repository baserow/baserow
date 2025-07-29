# Baserow Documentation

Source: https://baserow.io/user-docs/long-text-field

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Long text field

A long text field enables you to capture a lot of information in your table. Long text fields are best for storing data such as brief descriptions, notes, multiple lines of text, or a large amount of data in a single record.

Unlike the [single line text field](/user-docs/single-line-text-field), the long text field accepts more than one line of text. When you need to keep multiple lines of text in each row, a long text field is ideal as it allows you to add new lines.

Baserow supports Markdown for text formatting, offering [keyboard shortcuts](/user-docs/baserow-keyboard-shortcuts) and an editing toolbar for ease of use. Markdown is a lightweight markup language used to format plain text.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/9d6f1a39-8c6d-42f2-a202-c248cc03b00c/Screenshot_2022-07-13_at_18.45.04.png)

## How to add a long text field

To add a long text field,

  1. Click the plus sign `+` to the right of your existing fields.
  2. Select the long text field type and input the name of the field.
  3. Click **Create**.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/16c71526-9496-43e6-bb3b-d85eed0894e9/Screenshot_2022-07-13_at_19.25.44.png)

## Expand a long text field

You can increase the size of a cell to have plenty of space when working with a long text field. You can do this by clicking the [expand row icon](/user-docs/navigating-row-configurations) or by using the drag handle on the lower right of the cell. In the expanded view, you have more room to add content in a cell.

![enter image description here](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/2d3356b5-7262-4bab-9a23-c99b78dd1852/55bfad6eaad6609c1df0c0fc480c4c39b33c0631.webp)

Use the [keyboard shortcut](/user-docs/baserow-keyboard-shortcuts), `Shift` \+ `Enter` on grid view to exit from editing mode for the long text field.

## Rich text formatting in Baserow

With rich text formatting, you can style and format the content of the long text field type in various customizable ways. This includes style choices like using italics, changing font size and color, as well as adding hyperlinks or code blocks.

![Baserow Rich text formatting](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/65df26a3-a638-43d6-94b7-50d1daf413ba/Untitled.png)

### Enable rich text formatting

Rich text formatting is only available for the long text field type.

To enable rich text formatting for long text fields, follow these steps:

  1. Open the table containing the field you want to format.
  2. Find the dropdown arrow next to the field you want to enable rich text formatting for.
  3. Click on the **Edit field** option.
  4. If the selected field isn’t a long text field, change it to a long text field.
  5. Check the “Enable rich text formatting” box to activate rich text features.
  6. Save your changes.

Once rich text formatting is enabled, you can format your paragraphs and headers:

  1. Double-click on the cell within your preferred row.
  2. Expand the cell by clicking on the expand icon.
  3. After expanding, a black paragraph icon will appear in the left-hand corner.
  4. Click the paragraph icon to access a range of paragraph and header options.
  5. For text modifications: 
     * Double-click on the text you want to format.
     * Utilize the toolbar options or [keyboard shortcuts](/user-docs/baserow-keyboard-shortcuts) for bold (**Ctrl+B**), italic (**Ctrl+I**), strike (**Ctrl+S**), and underline (**Ctrl+U**).

![Styling rich text formatting in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/21dcd7b7-8438-46b4-b384-0f3cab58124f/New%20styling%20options%20for%20the%20long%20text%20field.png)

### Markdown reference table

Baserow also supports a Markdown version for rich text formatting.

Markdown is supported for headings, bold, italic, strikethrough, unordered lists, ordered lists, hyperlinks, blockquotes, and code blocks in long text fields with rich text enabled.

You can format your text using Markdown keyboard shortcuts, or an editing toolbar that appears when you open a row in the long text field.

Styling |  |   
---|---|---  
Headings | # H1 heading   
## H2 sub-heading   
### H3 sub-heading | The numbers of `#` characters denote the hierarchy of the heading, ranging from first-level to third-level.  
Bold | ** This text will be bold **   
__ This text will be bold __ | Enclose text in `**` or `__` for bold formatting.  
Italic | *This text will be italic*   
_This text will be italic_ | Enclose text in `*` or `_` for italic formatting.  
Bold italic | _**This text will be bold italic**_ | Text surrounded by a single `_` and a double `**` will be formatted as bold italic — meaning strong emphasis in Markdown.  
Underline | <u>This text will be underlined</u> | Enclose text in `<u>` and `</u>` for underline formatting.  
Strikethrough | ~~This text will be strickenthrough~~ | Enclose text in `~~` for strikethrough.  
Blockquotes | >This will be a blockquote | Use `>` for blockquotes.  
Code blocks | ```  
code block  
``` | Use triple backticks ``` followed by the return/enter key for code blocks.  
Bulleted list | \- Bulleted list item | Type `-` at the beginning of your text to create a bulleted list.  
Numbered list | 1\. Numbered list item | Type `1.` to create a numbered list.  
Checkbox | \- [x] Checked   
\- [ ] Unchecked | Each checkbox is represented by `- [ ]` for unchecked and `- [x]` for checked.  
Hyperlink | [This is a link]([https://baserow.io/](/)) | Highlight the text you want to link, then click the link icon `♾` in the formatting toolbar. A dialog box will appear for you to input the URL. Once confirmed, your text will transform into a clickable link. Learn more about [working with links in Baserow](/user-docs/url-field).  
Mention | @Bram | Type `@` followed by a collaborator’s name to send them a notification. Learn more about [mentions in Baserow](/user-docs/row-commenting).  
  
![Enable rich text formatting in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d13ff9d2-0194-48e5-8086-5ce0e6a5b039/Untitled%201.png)

### Rich text formatting in forms

Rich text in forms also supports the same paragraph styles and formatting available in regular fields with rich text enabled.

### Rich text formatting in the formula field

You can also include long text fields in [formulas](/user-docs/formula-field-overview). Formulas with long text fields with rich text enabled will display only the text and line breaks.

## Related content

  * [Single line text field](/user-docs/single-line-text-field)
  * [Field overview](/user-docs/baserow-field-overview)
  * [Add a new field](/user-docs/adding-a-field)
  * [Field configuration options](/user-docs/field-customization)

