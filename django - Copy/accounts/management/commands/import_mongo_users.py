from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from pymongo import MongoClient


class Command(BaseCommand):
    help = "Import users from old MongoDB (shoe.user) into Django auth_user."

    def add_arguments(self, parser):
        parser.add_argument("--mongo", default="mongodb://localhost:27017/shoe", help="MongoDB URI")

    def handle(self, *args, **options):
        client = MongoClient(options["mongo"])
        db = client.get_default_database()
        # thực tế DB của bạn đang dùng collection "users"
        col = db.get_collection("users")

        created = 0
        updated = 0
        for doc in col.find({}):
            email = (doc.get("email") or "").strip().lower()
            if not email:
                continue
            fullname = (doc.get("fullname") or "").strip()
            phone = doc.get("phone")
            is_admin = bool(doc.get("isAdmin") or False)
            bcrypt_hash = (doc.get("password") or "").strip()

            user, was_created = User.objects.get_or_create(username=email, defaults={"email": email})
            user.email = email
            user.first_name = fullname[:150] if fullname else user.first_name
            user.is_staff = is_admin
            # Nếu bạn muốn admin Mongo trở thành superuser Django luôn:
            user.is_superuser = is_admin

            # Giữ đăng nhập được: lưu password theo định dạng BCryptPasswordHasher
            # Node hash: $2a$/$2b$...
            if bcrypt_hash.startswith("$2"):
                user.password = "bcrypt$" + bcrypt_hash
            else:
                # fallback: không dùng được password cũ
                user.set_unusable_password()

            user.save()

            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Done. created={created}, updated={updated}"))

