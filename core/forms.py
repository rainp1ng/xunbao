from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Community, MarketListing, TreasureTask


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class LoginForm(AuthenticationForm):
    pass


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(
        label="当前密码",
        widget=forms.PasswordInput(),
    )
    new_password1 = forms.CharField(
        label="新密码",
        widget=forms.PasswordInput(),
    )
    new_password2 = forms.CharField(
        label="确认新密码",
        widget=forms.PasswordInput(),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old_password = self.cleaned_data.get("old_password")
        if not self.user.check_password(old_password):
            raise forms.ValidationError("当前密码不正确")
        return old_password

    def clean_new_password2(self):
        password1 = self.cleaned_data.get("new_password1")
        password2 = self.cleaned_data.get("new_password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("两次输入的新密码不一致")
        return password2

    def save(self):
        self.user.set_password(self.cleaned_data["new_password1"])
        self.user.save()
        return self.user


class CommunityForm(forms.ModelForm):
    class Meta:
        model = Community
        fields = ("name", "description")


class TreasureTaskForm(forms.ModelForm):
    assignee_username = forms.CharField(
        required=False,
        help_text="可选：指定执行者用户名（指定后任务自动变为进行中）",
    )
    publish_at = forms.DateTimeField(
        required=False,
        help_text="可选：发布时间（不填则立即发布）",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    expire_at = forms.DateTimeField(
        required=False,
        help_text="可选：过期时间（过期后奖励减半，创建者受积分惩罚）",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )

    class Meta:
        model = TreasureTask
        fields = ("title", "description", "value_points", "assignee_username", "publish_at", "expire_at")


class MarketListingForm(forms.ModelForm):
    class Meta:
        model = MarketListing
        fields = ("title", "description", "price_points")


class BankExchangeForm(forms.Form):
    gold = forms.IntegerField(min_value=0, required=False, initial=0, label="兑换金币数量")
    silver = forms.IntegerField(min_value=0, required=False, initial=0, label="兑换银币数量")

    def clean(self):
        cleaned = super().clean()
        gold = cleaned.get("gold") or 0
        silver = cleaned.get("silver") or 0
        if gold == 0 and silver == 0:
            raise forms.ValidationError("请至少填写一种货币的兑换数量")
        return cleaned


def _bootstrapify(form):
    for name, field in form.fields.items():
        widget = field.widget
        cls = widget.attrs.get("class", "")
        if isinstance(widget, (forms.TextInput, forms.EmailInput, forms.PasswordInput, forms.NumberInput)):
            widget.attrs["class"] = (cls + " form-control").strip()
        elif isinstance(widget, forms.Textarea):
            widget.attrs["class"] = (cls + " form-control").strip()
            widget.attrs.setdefault("rows", 4)
        elif isinstance(widget, forms.DateTimeInput):
            widget.attrs["class"] = (cls + " form-control").strip()
        elif isinstance(widget, forms.Select):
            widget.attrs["class"] = (cls + " form-select").strip()
    return form


def register_form(*args, **kwargs) -> RegisterForm:
    return _bootstrapify(RegisterForm(*args, **kwargs))


def login_form(*args, **kwargs) -> LoginForm:
    return _bootstrapify(LoginForm(*args, **kwargs))


def task_form(*args, **kwargs) -> TreasureTaskForm:
    return _bootstrapify(TreasureTaskForm(*args, **kwargs))


def change_password_form(*args, **kwargs) -> ChangePasswordForm:
    return _bootstrapify(ChangePasswordForm(*args, **kwargs))


def community_form(*args, **kwargs) -> CommunityForm:
    return _bootstrapify(CommunityForm(*args, **kwargs))


def market_form(*args, **kwargs) -> MarketListingForm:
    return _bootstrapify(MarketListingForm(*args, **kwargs))


def bank_form(*args, **kwargs) -> BankExchangeForm:
    return _bootstrapify(BankExchangeForm(*args, **kwargs))
