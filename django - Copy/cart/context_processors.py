from .models import Cart


def cart_badge(request):
    count = 0
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        if cart:
            count = sum(int(i.quantity) for i in cart.items.all())
    return {"cart_item_count": count}
