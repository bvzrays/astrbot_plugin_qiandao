# astrbot_plugin_qiandao

简单的签到插件：随机奖励积分或元宝（二选一）、兑换、排行。

## 指令
- /签到 或 /打卡
- /兑换积分 N
- /兑换元宝 N
- /签到排行 [月度|周排行]（默认月度）
- /签到重置（仅重置本人）

## 配置 _conf_schema.json
- reward_points_min/max：积分奖励范围
- reward_ingot_min/max：元宝奖励范围
- reward_points_prob：积分奖励概率（0-1）
- exchange_admin_only：是否仅管理员可兑换

将本插件目录放置到 AstrBot/data/plugins 下，启动 AstrBot 后在 WebUI 插件管理启用。
