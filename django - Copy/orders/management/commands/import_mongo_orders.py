from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from pymongo import MongoClient

from catalog.models import Product
from orders.models import Order, OrderItem


class Command(BaseCommand):
    help = "Import payments (orders) from old MongoDB (shoe.payment) into Django orders."

    def add_arguments(self, parser):
        parser.add_argument("--mongo", default="mongodb://localhost:27017/shoe", help="MongoDB URI")

    def handle(self, *args, **options):
        client = MongoClient(options["mongo"])
        db = client.get_default_database()
        # thực tế DB của bạn đang dùng collection "payments"
        col = db.get_collection("payments")

        created = 0
        for doc in col.find({}):
            email = (doc.get("user") or "").strip().lower()
            if not email:
                continue
            user, _ = User.objects.get_or_create(username=email, defaults={"email": email})

            total = int(doc.get("sumprice") or 0)
            is_paid = bool(doc.get("trangthai") or False)
            delivered = bool(doc.get("tinhtrang") or False)

            order = Order.objects.create(
                user=user,
                full_name=(doc.get("username") or user.first_name or email)[:255],
                phone=str(doc.get("phone") or ""),
                address=(doc.get("address") or "")[:500],
                payment_method=Order.PaymentMethod.VNPAY if is_paid else Order.PaymentMethod.COD,
                is_paid=is_paid,
                status=Order.Status.DONE if delivered else Order.Status.PLACED,
                total=total,
                note="(imported from MongoDB)",
            )

            for p in doc.get("products") or []:
                name = (p.get("nameProduct") or "").strip()
                price = int(p.get("price") or 0)
                qty = int(p.get("quantity") or 0)
                size = str(p.get("size") or "")

                if not name:
                    continue

                # Mongo cart/payment không có productId -> match theo slug/name, nếu không có thì tạo placeholder product
                prod = Product.objects.filter(name__iexact=name).first()
                if not prod:
                    prod = Product.objects.create(
                        name=name,
                        slug=slugify(name)[:255] or f"import-{order.id}",
                        price=price,
                        description="(imported from MongoDB order item)",
                        type=int(p.get("type") or 0),
                    )

                OrderItem.objects.create(
                    order=order,
                    product=prod,
                    quantity=max(1, qty),
                    size=size,
                    price=price,
                )

            created += 1
            if created % 50 == 0:
                self.stdout.write(f"Imported {created} orders...")

        self.stdout.write(self.style.SUCCESS(f"Done. Imported {created} orders."))

