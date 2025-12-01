from django_cte import CTEManager


def make_trash_manager(trashed, parent=None):
    """
    Constructs a Django Queryset Manager which filters down it's base queryset according
    to the provided parameters.

    We need to use a method to construct a closed class rather than say, __init__
    parameters given to a single base class as Django will init a models managers
    without providing any kwargs breaking things horribly. This way django can init
    the manager without providing any kwargs and it will still filter correctly.

    :param trashed: If true the manager will only return trashed entries, if false then
        only returns non-trashed entries.
    :param parent: If specified will use the trashed column in a related model where
        parent is the name of the FK to the related model.
    :return: A manager with an override get_queryset filtered accordingly.
    """

    filter_kwargs = {}

    if parent is None:
        filter_kwargs["trashed"] = trashed
    else:
        filter_kwargs[f"{parent}__trashed"] = trashed

    class Manager(CTEManager):
        def get_queryset(self):
            return super().get_queryset().filter(**filter_kwargs)

    return Manager


TrashOnlyManager = make_trash_manager(trashed=True)
NoTrashManager = make_trash_manager(trashed=False)
