from baserow.core.models import Template, TemplateCategory


class TemplateFixtures:
    def create_template_category(self, template=None, templates=None, **kwargs):
        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        category = TemplateCategory.objects.create(**kwargs)

        if not templates:
            templates = []

        if template:
            templates.append(template)

        category.templates.add(*templates)

        return category

    def create_template(self, category=None, categories=None, **kwargs):
        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "slug" not in kwargs:
            kwargs["slug"] = self.fake.slug()

        if "icon" not in kwargs:
            kwargs["icon"] = "document"

        if "workspace" not in kwargs:
            kwargs["workspace"] = self.create_workspace()

        template = Template.objects.create(**kwargs)

        if not categories:
            categories = []

        if category:
            categories.append(category)

        if len(categories) == 0:
            categories.append(self.create_template_category())

        template.categories.add(*categories)

        return template
