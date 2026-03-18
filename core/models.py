import math
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import F
from django.utils import timezone


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    points = models.PositiveIntegerField(default=0)
    gold = models.PositiveIntegerField(default=0)
    silver = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.user.username}({self.points}积分)"


class Community(models.Model):
    """社群"""
    name = models.CharField(max_length=100, verbose_name="社群名称")
    description = models.TextField(blank=True, verbose_name="社群描述")
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_communities", verbose_name="群主")
    members = models.ManyToManyField(User, through="CommunityMembership", related_name="communities", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_member(self, user: User) -> bool:
        return self.members.filter(id=user.id).exists()

    def is_admin(self, user: User) -> bool:
        """判断是否是管理员（包括群主）"""
        if self.creator_id == user.id:
            return True
        return self.memberships.filter(user=user, is_admin=True).exists()

    def is_owner(self, user: User) -> bool:
        """判断是否是群主"""
        return self.creator_id == user.id

    def admin_count(self) -> int:
        """管理员数量（不包括群主）"""
        return self.memberships.filter(is_admin=True).count()

    def can_add_admin(self) -> bool:
        """是否可以添加管理员"""
        return self.admin_count() < 5

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "社群"
        verbose_name_plural = "社群"


class CommunityMembership(models.Model):
    """社群成员"""
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="community_memberships")
    is_admin = models.BooleanField(default=False, verbose_name="是否管理员")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("community", "user")
        verbose_name = "社群成员"
        verbose_name_plural = "社群成员"


class JoinRequest(models.Model):
    """入群申请"""
    STATUS_CHOICES = [
        ("pending", "待审批"),
        ("approved", "已通过"),
        ("rejected", "已拒绝"),
    ]
    
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="join_requests")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="join_requests")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    message = models.TextField(blank=True, verbose_name="申请留言")
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="processed_requests")

    class Meta:
        unique_together = ("community", "user")
        verbose_name = "入群申请"
        verbose_name_plural = "入群申请"


class TreasureTask(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "可领取"
        CLAIMED = "claimed", "进行中"
        COMPLETED = "completed", "已完成"

    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    value_points = models.PositiveIntegerField(default=0)

    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_tasks")
    assignee = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tasks",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    
    # 发布时间和过期时间
    publish_at = models.DateTimeField(null=True, blank=True, verbose_name="发布时间")
    expire_at = models.DateTimeField(null=True, blank=True, verbose_name="过期时间")
    
    # 社群关联（为空则公开可见）
    community = models.ForeignKey(
        Community,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
        verbose_name="所属社群"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completion_proof = models.TextField(blank=True, verbose_name="完成证明")
    
    # 记录已扣惩罚天数
    penalty_days_applied = models.PositiveIntegerField(default=0)

    def is_visible_to(self, user: User) -> bool:
        """判断任务是否对用户可见"""
        if not self.community:
            return True
        return self.community.is_member(user)

    def get_current_reward(self) -> int:
        """计算当前实际奖励积分（过期后每天减半）"""
        if not self.expire_at or timezone.now() <= self.expire_at:
            return self.value_points
        
        days_expired = (timezone.now() - self.expire_at).days
        reward = self.value_points
        for _ in range(days_expired):
            reward = reward // 2
            if reward == 0:
                break
        return reward

    def get_current_penalty(self) -> int:
        """计算当前惩罚积分（过期后每天惩罚1/4，向上取整）"""
        if not self.expire_at or timezone.now() <= self.expire_at:
            return 0
        
        days_expired = (timezone.now() - self.expire_at).days
        daily_penalty = math.ceil(self.value_points / 4)
        return daily_penalty * days_expired

    def apply_daily_penalty(self) -> int:
        """应用每日惩罚（扣除创建者积分）"""
        if not self.expire_at or self.status == self.Status.COMPLETED:
            return 0
        
        now = timezone.now()
        if now <= self.expire_at:
            return 0
        
        days_expired = (now - self.expire_at).days
        if days_expired <= self.penalty_days_applied:
            return 0
        
        days_to_charge = days_expired - self.penalty_days_applied
        daily_penalty = math.ceil(self.value_points / 4)
        total_penalty = daily_penalty * days_to_charge
        
        Profile.objects.filter(user_id=self.creator_id).update(
            points=F("points") - total_penalty
        )
        
        self.penalty_days_applied = days_expired
        self.save(update_fields=["penalty_days_applied"])
        
        return total_penalty

    def can_claim(self, user: User) -> bool:
        if self.status != self.Status.OPEN:
            return False
        if self.assignee_id is not None and self.assignee_id != user.id:
            return False
        if self.creator_id == user.id:
            return False
        # 社群任务只有成员可以领取
        if self.community and not self.community.is_member(user):
            return False
        return True

    def claim(self, user: User) -> None:
        if not self.can_claim(user):
            raise ValueError("该任务不可领取")
        self.assignee = user
        self.status = self.Status.CLAIMED

    def can_complete(self, user: User) -> bool:
        return self.status == self.Status.CLAIMED and self.assignee_id == user.id

    def complete_and_reward(self) -> int:
        if self.status != self.Status.CLAIMED or self.assignee_id is None:
            raise ValueError("该任务不可完成")
        actual_reward = self.get_current_reward()
        Profile.objects.filter(user_id=self.assignee_id).update(points=F("points") + actual_reward)
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        return actual_reward

    def __str__(self) -> str:
        return f"{self.title}({self.value_points})"


class MarketListing(models.Model):
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price_points = models.PositiveIntegerField(default=0)

    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name="market_listings")
    is_active = models.BooleanField(default=True)

    buyer = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="purchases"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sold_at = models.DateTimeField(null=True, blank=True)

    def can_buy(self, user: User) -> bool:
        return self.is_active and self.seller_id != user.id and self.buyer_id is None

    def buy(self, buyer: User) -> None:
        if not self.can_buy(buyer):
            raise ValueError("该商品不可购买")
        updated = Profile.objects.filter(user=buyer, points__gte=self.price_points).update(
            points=F("points") - self.price_points
        )
        if updated != 1:
            raise ValueError("积分不足")
        Profile.objects.filter(user=self.seller).update(points=F("points") + self.price_points)
        self.buyer = buyer
        self.is_active = False
        self.sold_at = timezone.now()

    def __str__(self) -> str:
        return f"{self.title}({self.price_points})"
