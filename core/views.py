from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import F, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import bank_form, community_form, login_form, market_form, register_form, task_form
from .models import Community, CommunityMembership, MarketListing, Profile, TreasureTask


def home(request: HttpRequest) -> HttpResponse:
    tasks = TreasureTask.objects.exclude(status="completed")
    
    if request.user.is_authenticated:
        # 公开任务 + 用户所属社群的任务
        user_communities = Community.objects.filter(members=request.user)
        tasks = tasks.filter(Q(community__isnull=True) | Q(community__in=user_communities))
    else:
        # 未登录只看公开任务
        tasks = tasks.filter(community__isnull=True)
    
    tasks = tasks.select_related("creator", "assignee", "community").order_by("-created_at")[:50]
    
    # 应用过期惩罚检查
    for task in tasks:
        if task.expire_at and task.status == TreasureTask.Status.OPEN:
            task.apply_daily_penalty()
    
    return render(request, "core/home.html", {"tasks": tasks})


def register(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = register_form(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "注册成功，欢迎来到寻宝。")
            return redirect("home")
    else:
        form = register_form()
    return render(request, "core/register.html", {"form": form})


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = login_form(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "登录成功。")
            return redirect(request.GET.get("next") or "home")
    else:
        form = login_form(request)
    return render(request, "core/login.html", {"form": form})


@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.info(request, "已退出登录。")
    return redirect("home")


def task_detail(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(TreasureTask.objects.select_related("creator", "assignee", "community"), pk=pk)
    
    # 检查可见性
    if task.community and not task.community.is_member(request.user):
        messages.error(request, "你没有权限查看此任务。")
        return redirect("home")
    
    # 应用过期惩罚检查
    if task.expire_at and task.status == TreasureTask.Status.OPEN:
        task.apply_daily_penalty()
    
    # 计算过期相关数据
    is_expired = False
    current_reward = task.value_points
    current_penalty = 0
    
    if task.expire_at and timezone.now() > task.expire_at:
        is_expired = True
        current_reward = task.get_current_reward()
        current_penalty = task.get_current_penalty()
    
    return render(request, "core/task_detail.html", {
        "task": task,
        "is_expired": is_expired,
        "current_reward": current_reward,
        "current_penalty": current_penalty,
    })


@login_required
def task_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = task_form(request.POST, user=request.user)
        if form.is_valid():
            assignee_username = (form.cleaned_data.get("assignee_username") or "").strip()
            assignee = None
            if assignee_username:
                assignee = User.objects.filter(username=assignee_username).first()
                if not assignee:
                    form.add_error("assignee_username", "该用户名不存在")
                    return render(request, "core/task_form.html", {"form": form})
            
            # 处理社群
            community_id = form.cleaned_data.get("community_id")
            community = None
            if community_id:
                try:
                    community = Community.objects.get(pk=community_id, members=request.user)
                except Community.DoesNotExist:
                    form.add_error("community_id", "你不在该社群中")
                    return render(request, "core/task_form.html", {"form": form})
            
            task: TreasureTask = form.save(commit=False)
            task.creator = request.user
            task.assignee = assignee
            task.community = community
            
            # 如果指定了执行者，自动设为进行中
            if assignee:
                task.status = TreasureTask.Status.CLAIMED
            else:
                task.status = TreasureTask.Status.OPEN
            
            task.save()
            messages.success(request, "藏宝成功，宝藏盒子已出现。")
            return redirect("task_detail", pk=task.pk)
    else:
        form = task_form(user=request.user)
    
    # 获取用户所属社群
    communities = Community.objects.filter(members=request.user)
    
    return render(request, "core/task_form.html", {"form": form, "communities": communities})


@login_required
@require_POST
def task_claim(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(TreasureTask, pk=pk)
    try:
        with transaction.atomic():
            task = TreasureTask.objects.select_for_update().get(pk=pk)
            task.claim(request.user)
            task.save(update_fields=["assignee", "status"])
        messages.success(request, "领取成功，开始寻宝吧。")
    except Exception as e:
        messages.error(request, f"领取失败：{e}")
    return redirect("task_detail", pk=pk)


@login_required
@require_POST
def task_complete(request: HttpRequest, pk: int) -> HttpResponse:
    proof = (request.POST.get("proof") or "").strip()
    try:
        with transaction.atomic():
            task = TreasureTask.objects.select_for_update().get(pk=pk)
            if not task.can_complete(request.user):
                raise ValueError("你无权完成该任务")
            if not proof:
                raise ValueError("请填写完成任务的证明")
            actual_reward = task.complete_and_reward()
            task.completion_proof = proof
            task.save(update_fields=["status", "completed_at", "completion_proof"])
        
        original_reward = task.value_points
        if actual_reward < original_reward:
            messages.success(request, f"任务完成，获得 {actual_reward} 积分（原奖励 {original_reward}，因过期已减半）。")
        else:
            messages.success(request, "任务完成，积分已到账。")
    except TreasureTask.DoesNotExist:
        messages.error(request, "任务不存在")
    except Exception as e:
        messages.error(request, f"完成失败：{e}")
    return redirect("task_detail", pk=pk)


@login_required
def my_created_tasks(request: HttpRequest) -> HttpResponse:
    tasks = (
        TreasureTask.objects.filter(creator=request.user)
        .select_related("assignee", "community")
        .order_by("-created_at")
    )
    
    for task in tasks:
        if task.expire_at and task.status == TreasureTask.Status.OPEN:
            task.apply_daily_penalty()
    
    return render(request, "core/my_created_tasks.html", {"tasks": tasks})


@login_required
def my_assigned_tasks(request: HttpRequest) -> HttpResponse:
    tasks = (
        TreasureTask.objects.filter(assignee=request.user)
        .select_related("creator", "community")
        .order_by("-created_at")
    )
    return render(request, "core/my_assigned_tasks.html", {"tasks": tasks})


# ========== 社群相关视图 ==========

@login_required
def community_list(request: HttpRequest) -> HttpResponse:
    """社群列表"""
    communities = Community.objects.all().order_by("-created_at")
    
    # 标记用户是否已加入
    user_communities = set(
        CommunityMembership.objects.filter(user=request.user).values_list("community_id", flat=True)
    )
    
    return render(request, "core/community_list.html", {
        "communities": communities,
        "user_communities": user_communities,
    })


@login_required
def community_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """社群详情"""
    community = get_object_or_404(Community, pk=pk)
    is_member = community.is_member(request.user)
    
    # 社群任务（只有成员可见）
    tasks = []
    if is_member:
        tasks = TreasureTask.objects.filter(community=community).select_related("creator", "assignee").order_by("-created_at")[:20]
    
    members = community.member_set.all().select_related("user")
    
    return render(request, "core/community_detail.html", {
        "community": community,
        "is_member": is_member,
        "tasks": tasks,
        "members": members,
    })


@login_required
def community_create(request: HttpRequest) -> HttpResponse:
    """创建社群"""
    if request.method == "POST":
        form = community_form(request.POST)
        if form.is_valid():
            community: Community = form.save(commit=False)
            community.creator = request.user
            community.save()
            # 创建者自动加入
            CommunityMembership.objects.create(community=community, user=request.user)
            messages.success(request, f"社群「{community.name}」创建成功！")
            return redirect("community_detail", pk=community.pk)
    else:
        form = community_form()
    return render(request, "core/community_form.html", {"form": form})


@login_required
@require_POST
def community_join(request: HttpRequest, pk: int) -> HttpResponse:
    """加入社群"""
    community = get_object_or_404(Community, pk=pk)
    if community.is_member(request.user):
        messages.warning(request, "你已经是该社群成员了。")
    else:
        CommunityMembership.objects.create(community=community, user=request.user)
        messages.success(request, f"已加入社群「{community.name}」！")
    return redirect("community_detail", pk=pk)


@login_required
@require_POST
def community_leave(request: HttpRequest, pk: int) -> HttpResponse:
    """退出社群"""
    community = get_object_or_404(Community, pk=pk)
    CommunityMembership.objects.filter(community=community, user=request.user).delete()
    messages.info(request, f"已退出社群「{community.name}」。")
    return redirect("community_list")


# ========== 市场相关视图 ==========

def market_list(request: HttpRequest) -> HttpResponse:
    listings = (
        MarketListing.objects.select_related("seller", "buyer").order_by("-created_at")[:50]
    )
    return render(request, "core/market_list.html", {"listings": listings})


def market_detail(request: HttpRequest, pk: int) -> HttpResponse:
    listing = get_object_or_404(MarketListing.objects.select_related("seller", "buyer"), pk=pk)
    return render(request, "core/market_detail.html", {"listing": listing})


@login_required
def market_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = market_form(request.POST)
        if form.is_valid():
            listing: MarketListing = form.save(commit=False)
            listing.seller = request.user
            listing.save()
            messages.success(request, "上架成功。")
            return redirect("market_detail", pk=listing.pk)
    else:
        form = market_form()
    return render(request, "core/market_form.html", {"form": form})


@login_required
@require_POST
def market_buy(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        with transaction.atomic():
            listing = MarketListing.objects.select_for_update().get(pk=pk)
            listing.buy(request.user)
            listing.save(update_fields=["buyer", "is_active", "sold_at"])
        messages.success(request, "购买成功。")
    except MarketListing.DoesNotExist:
        messages.error(request, "商品不存在")
    except Exception as e:
        messages.error(request, f"购买失败：{e}")
    return redirect("market_detail", pk=pk)


@login_required
def bank(request: HttpRequest) -> HttpResponse:
    profile = request.user.profile
    points_per_gold = int(getattr(settings, "XUNBAO_POINTS_PER_GOLD", 100))
    points_per_silver = int(getattr(settings, "XUNBAO_POINTS_PER_SILVER", 10))

    if request.method == "POST":
        form = bank_form(request.POST)
        if form.is_valid():
            gold = form.cleaned_data.get("gold") or 0
            silver = form.cleaned_data.get("silver") or 0
            need_points = gold * points_per_gold + silver * points_per_silver
            try:
                with transaction.atomic():
                    updated = Profile.objects.filter(user=request.user, points__gte=need_points).update(
                        points=F("points") - need_points,
                        gold=F("gold") + gold,
                        silver=F("silver") + silver,
                    )
                    if updated != 1:
                        raise ValueError("积分不足")
                messages.success(
                    request,
                    f"兑换成功：-{need_points}积分，+{gold}金币，+{silver}银币。",
                )
                return redirect("bank")
            except Exception as e:
                messages.error(request, f"兑换失败：{e}")
    else:
        form = bank_form()

    return render(
        request,
        "core/bank.html",
        {
            "form": form,
            "profile": profile,
            "points_per_gold": points_per_gold,
            "points_per_silver": points_per_silver,
        },
    )
