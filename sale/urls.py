from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/your-items", views.vendor_items, name="vendor-items"),
    path("home/", views.home, name="home"),
    path("item/add", views.AddItem.as_view(), name="add-item"),
    path("item/edit/<int:pk>/", views.EditItem.as_view(), name="edit-item"),
    path("item/delete/<int:pk>/", views.DeleteItem.as_view(), name="delete-item"),
    path("wallet/", views.wallet, name="wallet"),
    path("wallet/add-money/", views.AddMoney.as_view(), name="add-money"),
    path("item/<int:item_id>/", views.item_detail, name="item-detail"),
    path("item/review/<int:item_id>", views.leave_review, name="leave-review"),
    path("item/random/", views.random_item, name="random-item"),
    path("sales-report/", views.sales_report, name="sales-report"),
    path('ajax/search-suggestions/', views.ajax_search_suggestions, name='ajax_search_suggestions'),
]
# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
