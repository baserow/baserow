# Emails

## Creating a new email template

Baserow uses [MJML](https://mjml.io/) framework to define email templates. These templates have to be compiled into their HTML versions so that they can be used by Django.

Start by creating a new template (`*.mjml.eta`) in the core email template folder (`backend/src/baserow/core/templates/baserow`) or in the template folder of the contrib module that the template belongs to.

The template should be in MJML format and will typically inherit a base layout (`base.layout.eta`) common to all emails. Besides formatting itself, the template should be a normal Django template, using the Django template language, and should utilize standard Django syntax for translations.

The template will look something like this:

```html
<% layout("../base.layout.eta") %>

<mj-section>
  <mj-column>
    <mj-text mj-class="title">{% trans "Title to be translated" %}</mj-text>
    <mj-text mj-class="text">
      {% blocktrans trimmed %}
        Text to be translated
      {% endblocktrans %}
    </mj-text>
    <mj-button mj-class="button" href="{{ some_link_passed_as_context_variable }}">
      {% trans "Link text to be translated" %}
    </mj-button>
  </mj-column>
</mj-section>
```

If you are using the Baserow Docker Compose development environment (`just dc-dev up -d`), the new template should be automatically compiled into its HTML version, resulting in a new file. If that's not the case, follow the instructions in `backend/email_compiler` to compile the template manually.

### Do

- Make sure the received email has both HTML and plain text version.
- Make sure the whole content of the email template is translatable.
- Make sure the links lead correctly to Baserow instance without hard-coding the URL.

### Don't

- Don't edit HTML email templates directly, edit the MJML templates instead and recompile them.

## Sending emails

Subclass `BaseEmailMessage` to define an email message with the correct template and all the needed parameters.

### Do

- Send emails in background Celery tasks.
- Use `with translation.override(user.profile.language)` to send emails in the user's selected language.

## Testing

The Baserow dev environment automatically starts an instance of [MailHog](https://github.com/mailhog/MailHog) at [http://localhost:8025/](http://localhost:8025/). You can verify that the emails are formatted and sent correctly there.

**Docker development:**
```bash
just dc-dev up -d    # MailHog is included
```

**Local development:**
```bash
just dev up          # MailHog runs via Docker
```
