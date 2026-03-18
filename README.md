# 寻宝（xunbao）

一个用 Python/Django 开发的轻量 Web 应用原型：藏宝（发任务）/寻宝（领取完成得积分）/交易所（摆摊买卖）/钱庄（积分兑换货币）。

## 本地运行

在项目根目录执行：

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

浏览器打开 `http://127.0.0.1:8000/`。

## 功能入口

- **宝藏任务**：`/`  
  - 未登录可浏览任务列表/详情
  - 登录后可“藏宝”（发任务）、“寻宝”（领取/完成任务得积分）
- **交易所**：`/market/`  
  - 登录后可上架商品、购买商品（用积分结算）
- **钱庄**：`/bank/`  
  - 登录后可将积分兑换为金币/银币
- **后台管理**：`/admin/`  
  - 需要创建管理员账号：

```bash
. .venv/bin/activate
python manage.py createsuperuser
```

## 规则（当前实现）

- **藏宝人**：创建任务时可指定执行者用户名（可留空代表任何人可领取）
- **寻宝人**：领取任务后可“完成任务”领取积分
- **交易所**：卖家上架商品；买家购买后积分从买家转给卖家
- **钱庄**：兑换汇率在 `xunbao/settings.py` 中：
  - `XUNBAO_POINTS_PER_GOLD`（默认 100）
  - `XUNBAO_POINTS_PER_SILVER`（默认 10）

