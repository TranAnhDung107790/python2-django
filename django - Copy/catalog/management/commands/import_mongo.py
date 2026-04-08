import os
from typing import Any

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from pymongo import MongoClient

from catalog.models import Product, ProductImage


class Command(BaseCommand):
    help = "Import products from old MongoDB (shoe.products) into Django."

    def add_arguments(self, parser):
        parser.add_argument("--mongo", default="mongodb://localhost:27017/shoe", help="MongoDB URI")

    def handle(self, *args, **options):
        mongo_uri = options["mongo"]
        client = MongoClient(mongo_uri)
        db = client.get_default_database()
        collection = db.get_collection("products")

        count = 0
        for doc in collection.find({}):
            name = (doc.get("name") or "").strip()
            if not name:
                continue

            raw_slug = (doc.get("slug") or "").strip()
            clean_slug = slugify(raw_slug) if raw_slug else slugify(name)
            if not clean_slug:
                clean_slug = slugify(f"product-{str(doc.get('_id'))}")

            product, _ = Product.objects.update_or_create(
                slug=clean_slug,
                defaults={
                    "name": name,
                    "description": doc.get("description") or "",
                    "price": int(doc.get("price") or 0),
                    "type": int(doc.get("type") or 0),
                },
            )

            # Import images if they exist on disk
            # Old system stores filenames in doc["img"] and served from Node uploads folder.
            img_names = doc.get("img") or []
            uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "server", "src", "uploads"))
            for img_name in img_names:
                if not img_name:
                    continue
                # Avoid duplicates
                if product.images.filter(image__endswith=f"/{img_name}").exists():
                    continue
                src = os.path.join(uploads_dir, img_name)
                if not os.path.exists(src):
                    continue
                with open(src, "rb") as f:
                    content = f.read()
                pi = ProductImage(product=product)
                pi.image.save(img_name, ContentFile(content), save=True)

            count += 1
            if count % 50 == 0:
                self.stdout.write(f"Imported {count} products...")

        self.stdout.write(self.style.SUCCESS(f"Done. Imported {count} products."))

