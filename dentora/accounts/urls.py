from django.urls import path

from dentora.accounts import views

app_name = "accounts"

urlpatterns = [
    # Authentication
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/refresh/", views.TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path(
        "auth/change-password/",
        views.ChangePasswordView.as_view(),
        name="change-password",
    ),
    # User management (admin only)
    path("users/", views.UserListCreateView.as_view(), name="user-list-create"),
]
