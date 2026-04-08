from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from pymongo import MongoClient

from cart.models import Cart, CartItem
from catalog.models import Product


class Command(BaseCommand):
    help = "Import carts from old MongoDB (shoe.carts) into Django cart."

    def add_arguments(self, parser):
        parser.add_argument("--mongo", default="mongodb://localhost:27017/shoe", help="MongoDB URI")

    def handle(self, *args, **options):
        db = MongoClient(options["mongo"]).get_default_database()
        col = db.get_collection("carts")

        imported = 0
        for doc in col.find({}):
            email = (doc.get("user") or "").strip().lower()
            if not email:
                continue

            user, _ = User.objects.get_or_create(username=email, defaults={"email": email})
            cart, _ = Cart.objects.get_or_create(user=user)
            cart.full_name = (doc.get("name") or "")[:255]
            cart.phone = str(doc.get("phone") or "")
            cart.address = (doc.get("address") or "")[:500]
            cart.save()

            # Replace current items by Mongo snapshot
            cart.items.all().delete()

            for p in doc.get("products") or []:
                name = (p.get("nameProduct") or "").strip()
                if not name:
                    continue
                price = int(p.get("price") or 0)
                qty = max(1, int(p.get("quantity") or 1))
                size = str(p.get("size") or "")
                ptype = int(p.get("type") or 0)

                prod = Product.objects.filter(name__iexact=name).first()
                if not prod:
                    prod = Product.objects.create(
                        name=name,
                        slug=slugify(name)[:255] or f"import-product-{user.id}",
                        price=price,
                        type=ptype,
                        description="(imported from MongoDB cart)",
                    )

                CartItem.objects.create(
                    cart=cart,
                    product=prod,
                    quantity=qty,
                    size=size,
                )

            imported += 1

        self.stdout.write(self.style.SUCCESS(f"Done. Imported {imported} carts."))

