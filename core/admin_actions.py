import csv

from django.http import HttpResponse


def export_as_csv_action(description='Export selected as CSV', fields=None, exclude=None, header=True):
    """Build an admin action that streams the selected rows as a CSV file.

    `fields` accepts an explicit list of column keys. Each key may be a model
    field name or the name of a callable defined on the model/admin. When
    omitted, every concrete model field is exported. Foreign keys are rendered
    with ``str()`` so the CSV stays human-readable.
    """
    def export_as_csv(modeladmin, request, queryset):
        opts = modeladmin.model._meta
        if fields is not None:
            field_names = list(fields)
        else:
            field_names = [
                f.name for f in opts.concrete_fields
                if f.name not in (exclude or ())
            ]

        labels = []
        for name in field_names:
            try:
                field = opts.get_field(name)
                labels.append(str(field.verbose_name).title())
            except Exception:
                labels.append(name.replace('_', ' ').title())

        response = HttpResponse(content_type='text/csv')
        filename = f'{opts.app_label}_{opts.model_name}_{request.user.pk}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        if header:
            writer.writerow(labels)

        for obj in queryset.iterator(chunk_size=500):
            row = []
            for name in field_names:
                value = getattr(obj, name)
                if callable(value):
                    value = value()
                if hasattr(value, 'pk'):
                    value = str(value)
                if value is None:
                    value = ''
                row.append(value)
            writer.writerow(row)
        return response

    export_as_csv.short_description = description
    return export_as_csv
