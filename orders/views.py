from django.shortcuts import render, redirect, get_object_or_404
from .models import Cart, CartItem, Order, OrderItem, Wishlist
from sale.models import Item
from Users.decorators import vendor_check, customer_check
from django.contrib import messages
from .forms import AddToCartForm
from django.db.models import F
import logging
logger = logging.getLogger(__name__)
# from django.core.mail import send_mail
from django.core.mail import EmailMessage , send_mail
# from django_mailjet import mail
# views.py
from django.db import transaction


# def add_to_cart(request, item_id):
#     item = Item.objects.select_for_update().get(pk=item_id)
    # Rest of your logic
@transaction.atomic
@customer_check
def add_to_cart(request, item_id):
    item = get_object_or_404(Item.objects.select_for_update(), pk=item_id)
    cart, created = Cart.objects.get_or_create(owner=request.user.customer)
    cart_item = CartItem.objects.filter(cart=cart, item=item).first()

    # Default quantity when adding directly from a button
    default_quantity = 1

    if cart_item:
        # If item is already in cart, just increment quantity
        cart_item.quantity += default_quantity
        cart_item.save()
        messages.success(
            request,
            f"Another {item.item_title} has been added to your cart. Total quantity: {cart_item.quantity}.",
        )
    else:
        # If item is not in cart, create a new CartItem
        CartItem.objects.create(cart=cart, item=item, quantity=default_quantity)
        messages.success(
            request, f"{default_quantity} {item.item_title} added to your cart."
        )

    # Always redirect to cart details after adding
    return redirect("cart-details")

@customer_check
def remove_from_cart(request, cart_item_id):
    cart_item = get_object_or_404(CartItem, pk=cart_item_id)

    if request.method == "POST":
        cart_item.delete()
        messages.success(request, f"{cart_item.item.item_title} removed from cart.")
        return redirect("cart-details")

    context = {"cart_item": cart_item}

    return render(request, "orders/remove_from_cart.html", context)



@customer_check
def cart_details(request):
    cart, created = Cart.objects.get_or_create(owner=request.user.customer)
    cart_items = cart.cart_items.all()
    

    for cart_item in cart_items:
        cart_item.total_iprice = cart_item.item.selling_price * cart_item.quantity
        # Check if item_stock is available and valid before comparison
        if cart_item.item.item_stock is not None:
            cart_item.stock_available = cart_item.item.item_stock >= cart_item.quantity
        else:
            # Handle cases where item_stock might be null or undefined
            cart_item.stock_available = False # Or some other default behavior

    context = {
        "cart": cart,
        "cart_items": cart_items,
    }

    return render(request, "orders/cart_details.html", context=context)

# --- New views for managing quantities in cart ---

@transaction.atomic
@customer_check
def update_cart_quantity(request, cart_item_id, action):
    cart_item = get_object_or_404(CartItem.objects.select_for_update(), pk=cart_item_id)
    
    # Ensure the cart item belongs to the current user's cart
    if cart_item.cart.owner != request.user.customer:
        messages.error(request, "You do not have permission to modify this cart item.")
        return redirect("cart-details")

    if request.method == "POST":
        if action == "increase":
            if cart_item.item.item_stock is None or cart_item.quantity < cart_item.item.item_stock:
                cart_item.quantity += 1
                cart_item.save()
                messages.success(request, f"Quantity of {cart_item.item.item_title} increased.")
            else:
                messages.warning(request, f"Maximum stock reached for {cart_item.item.item_title}.")
        elif action == "decrease":
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.save()
                messages.success(request, f"Quantity of {cart_item.item.item_title} decreased.")
            else:
                # If quantity becomes 0 or less, remove the item
                cart_item.delete()
                messages.info(request, f"{cart_item.item.item_title} removed from cart.")
        else:
            messages.error(request, "Invalid action.")
    else:
        messages.error(request, "Invalid request method.")

    return redirect("cart-details")

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

@customer_check
def create_order(request):
    cart = get_object_or_404(Cart, owner=request.user.customer)
    total_bill = cart.calculate_bill
    saving = cart.savings

    # Existing validation checks
    if request.user.balance < total_bill:
        messages.warning(request, "Insufficient balance to place the order.")
        return redirect("cart-details")
    if total_bill > 10**10:
        messages.warning(
            request,
            "In line with government regulations, We are unable to process orders greater than $1000000000!",
        )
        return redirect("cart-details")

    vendor_data = {}  # Stores vendor-specific data
    order_items = []

    # First pass: Validate stock and collect vendor data
    for cart_item in cart.cart_items.all():
        if cart_item.item.item_stock < cart_item.quantity:
            messages.warning(
                request, f"Insufficient stock for {cart_item.item.item_title}."
            )
            return redirect("cart-details")

        vendor = cart_item.item.vendor.user
        if vendor not in vendor_data:
            vendor_data[vendor] = {
                'balance_change': 0,
                'items': [],
                'email': cart_item.item.vendor.user.email
            }
        
        # Update vendor-specific data
        vendor_data[vendor]['balance_change'] += cart_item.quantity * cart_item.item.selling_price
        vendor_data[vendor]['items'].append(cart_item)

        # Update item stock
        cart_item.item.item_stock -= cart_item.quantity
        cart_item.item.item_orders += cart_item.quantity
        cart_item.item.save()

    # Create order
    order = Order.objects.create(
        customer=request.user.customer, 
        total_bill=total_bill, 
        saving=saving
    )

    # Create order items
    order_items = [
        OrderItem(
            order=order,
            item=cart_item.item,
            quantity=cart_item.quantity,
            item_price=cart_item.item.selling_price,
            item_title=cart_item.item.item_title,
        )
        for cart_item in cart.cart_items.all()
    ]
    OrderItem.objects.bulk_create(order_items)

    # Process vendors and send emails
    for vendor, data in vendor_data.items():
        # Update vendor balance
        vendor.balance = F("balance") + data['balance_change']
        vendor.save()

        # Prepare email content
        subject = f"R&A shop: New Order Received - Order #{order.pk}"
        context = {
            'order_id': order.pk,
            'customer_name': request.user.get_full_name(),
            'customer_email': request.user.email,
            'vendor_name': vendor.get_full_name(),
            'items': data['items'],
            'total_earnings': data['balance_change'],
            'order_date': order.order_date.strftime("%Y-%m-%d %H:%M:%S"),
        }

        html_content = render_to_string('orders/emails.html', context)
        text_content = strip_tags(html_content)

        try:
            # Create and send email
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=["mahmoudashawky197@gmail.com"],  # Send to vendor's email
                reply_to=[settings.DEFAULT_FROM_EMAIL]
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)
            
        except Exception as e:
            logger.error(f"Failed to send email to {data['email']}: {str(e)}")
            # Consider adding a fallback notification here
            
            # email.attach_alternative(html_content, "text/html")
            # email.send()

    # Update customer balance and clear cart
    request.user.balance -= total_bill
    request.user.save()
    cart.cart_items.all().delete()

    messages.success(request, "Order placed successfully.")
    return redirect("customer-order-details", order.pk)

@customer_check
def customer_order_details(request, order_id):
    order = get_object_or_404(Order, pk=order_id, customer=request.user.customer)
    order_items = order.order_items.all()
    for order_item in order_items:
        order_item.total_iprice = order_item.item_price * order_item.quantity
    context = {
        "order": order,
        "order_items": order_items,
    }
    return render(request, "orders/customer_order_details.html", context=context)


@customer_check
def customer_order_history(request):
    orders = Order.objects.filter(customer=request.user.customer).order_by("order_date")

    context = {
        "orders": orders,
    }
    return render(request, "orders/customer_order_history.html", context=context)


@vendor_check
def vendor_order_details(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    order_items = order.order_items.filter(item__vendor=request.user.vendor)
    total_earned = sum(item.item_price * item.quantity for item in order_items)
    for order_item in order_items:
        order_item.total_iprice = order_item.item_price * order_item.quantity

    context = {
        "order": order,
        "order_items": order_items,
        "total_earned": total_earned,
    }
    return render(request, "orders/vendor_order_details.html", context=context)


@vendor_check
def vendor_order_history(request):
    orders = (
        Order.objects.filter(order_items__item__vendor=request.user.vendor)
        .distinct()
        .order_by("order_date")
    )

    order_data = []
    for order in orders:
        order_items = order.order_items.filter(item__vendor=request.user.vendor)
        total_earned = sum(item.item_price * item.quantity for item in order_items)
        order_data.append(
            {
                "order": order,
                "total_earned": total_earned,
            }
        )

    context = {
        "order_data": order_data,
    }
    return render(request, "orders/vendor_order_history.html", context=context)


@customer_check
def add_to_wishlist(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    wishlist, created = Wishlist.objects.get_or_create(owner=request.user.customer)
    wishlist.items.add(item)
    messages.success(request, f"{item.item_title} added to your wishlist.")
    return redirect("wishlist")


@customer_check
def remove_from_wishlist(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    wishlist = get_object_or_404(Wishlist, owner=request.user.customer)
    wishlist.items.remove(item)
    messages.success(request, f"{item.item_title} removed from your wishlist.")
    return redirect("wishlist")


@customer_check
def wishlist(request):
    wishlist, created = Wishlist.objects.get_or_create(owner=request.user.customer)
    items = wishlist.items.all()
    context = {"items": items}
    return render(request, "orders/wishlist.html", context=context)
