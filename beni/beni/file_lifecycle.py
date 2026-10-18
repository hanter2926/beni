from django.db import transaction


def schedule_delete_if_unreferenced(file_field, *model_fields, storage=None):
    if isinstance(file_field, str):
        name = file_field
    else:
        name = getattr(file_field, 'name', None)
        storage = storage or getattr(file_field, 'storage', None)
    if not name or storage is None:
        return

    def delete_if_unreferenced():
        for model, field_name in model_fields:
            if model.objects.filter(**{field_name: name}).exists():
                return
        if storage.exists(name):
            storage.delete(name)

    transaction.on_commit(delete_if_unreferenced)
