from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    # 寻宝任务
    path("tasks/new/", views.task_create, name="task_create"),
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("tasks/<int:pk>/claim/", views.task_claim, name="task_claim"),
    path("tasks/<int:pk>/complete/", views.task_complete, name="task_complete"),
    path("my/created/", views.my_created_tasks, name="my_created_tasks"),
    path("my/assigned/", views.my_assigned_tasks, name="my_assigned_tasks"),
    # 交易所
    path("market/", views.market_list, name="market_list"),
    path("market/new/", views.market_create, name="market_create"),
    path("market/<int:pk>/", views.market_detail, name="market_detail"),
    path("market/<int:pk>/buy/", views.market_buy, name="market_buy"),
    # 钱庄
    path("bank/", views.bank, name="bank"),
]

