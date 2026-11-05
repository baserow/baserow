from baserow.core.subject.registries import subject_type_registry

for subject_type in subject_type_registry.get_all():
    subject_type.register_lifecycle_signals()
