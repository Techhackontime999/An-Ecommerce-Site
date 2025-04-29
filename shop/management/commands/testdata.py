import json
import os
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import models


class Command(BaseCommand):
    help = 'Automatically load all JSON files from the fixtures/ directory with priority'

    def handle(self, *args, **options):
        data_folder = os.path.join('shop', 'fixtures')

        if not os.path.exists(data_folder):
            self.stdout.write(self.style.ERROR(f"❌ Folder '{data_folder}' does not exist."))
            return

        # Correct and prioritized file loading order
        priority_files = [
            'category.json',    # ✅ Must match actual filename
            'sellers.json',
            'products.json',
        ]

        all_files = [f for f in os.listdir(data_folder) if f.endswith('.json')]
        files_to_load = [f for f in priority_files if f in all_files]

        # Warn about missing priority files
        for f in priority_files:
            if f not in all_files:
                self.stdout.write(self.style.WARNING(f"⚠️ Priority file '{f}' not found."))

        remaining_files = [f for f in all_files if f not in files_to_load]
        load_order = files_to_load + remaining_files

        if not load_order:
            self.stdout.write(self.style.WARNING("⚠️ No JSON files found to load."))
            return

        for file_name in load_order:
            file_path = os.path.join(data_folder, file_name)
            self.stdout.write(self.style.WARNING(f"📥 Loading data from {file_name}..."))

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        raise ValueError("File is empty")
                    data = json.loads(content)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error reading {file_name}: {e}"))
                continue

            for obj_data in data:
                model = obj_data.get('model')
                fields = obj_data.get('fields')

                if not model or not fields:
                    self.stdout.write(self.style.ERROR("❌ Invalid data format in JSON. Skipping entry."))
                    continue

                try:
                    app_label, model_name = model.split('.')
                    Model = apps.get_model(app_label, model_name)
                except Exception:
                    self.stdout.write(self.style.ERROR(f"❌ Model '{model}' not found. Skipping."))
                    continue

                # Resolve foreign keys
                for field_name, field_value in fields.items():
                    try:
                        field_object = Model._meta.get_field(field_name)
                        if isinstance(field_object, models.ForeignKey):
                            related_model = field_object.related_model
                            fields[field_name] = related_model.objects.get(pk=field_value)
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f"⚠️ Related object with pk={field_value} for field '{field_name}' not found. Skipping entry."
                        ))
                        break
                else:
                    instance = Model(**fields)
                    instance.pk = obj_data.get('pk')
                    instance.save()
                    self.stdout.write(self.style.SUCCESS(f"✅ Saved {model} with PK {instance.pk}"))

        self.stdout.write(self.style.SUCCESS("🎉 All JSON files loaded successfully!"))
