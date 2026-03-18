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

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completion_proof = models.TextField(blank=True, verbose_name="完成证明")

    def can_claim(self, user: User) -> bool:
        if self.status != self.Status.OPEN:
            return False
        if self.assignee_id is not None and self.assignee_id != user.id:
            return False
        if self.creator_id == user.id:
            return False
        return True

    def claim(self, user: User) -> None:
        if not self.can_claim(user):
            raise ValueError("该任务不可领取")
        self.assignee = user
        self.status = self.Status.CLAIMED

    def can_complete(self, user: User) -> bool:
        return self.status == self.Status.CLAIMED and self.assignee_id == user.id

    def complete_and_reward(self) -> None:
        if self.status != self.Status.CLAIMED or self.assignee_id is None:
            raise ValueError("该任务不可完成")
        Profile.objects.filter(user_id=self.assignee_id).update(points=F("points") + self.value_points)
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()

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
        # 扣买家积分、加卖家积分
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
