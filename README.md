## astrbot_plugin_qiandao · 签到/打卡（Napcat 风格）

---

### 插件亮点
- 随机奖励“积分/元宝”二选一，支持奖励概率与范围配置
- 支持管理员为他人兑换、查询；普通成员仅操作自己（可配置权限模式）
- 支持月/周签到天数排行，显示条数可配置
- 查询/结果消息可自定义标签与分隔线，内容更美观
- 数据自动迁移并持久化到统一目录，升级无忧

---

### 安装与启用
1. 将本插件文件夹放入 `AstrBot/data/plugins/astrbot_plugin_qiandao`（或以插件管理面板安装）。
2. 启动 AstrBot，在 WebUI 插件管理中启用本插件。
3. 配置项可在 WebUI 中图形化调整，修改后即时生效（无需重启）。

数据存储：`AstrBot/data/plugin-data/astrbot_plugin_qiandao/checkin_data.json`
- 首次运行会自动从旧路径 `data/plugins/astrbot_plugin_qiandao/checkin_data.json` 迁移数据。

---

### 指令说明
| 指令 | 作用 |
|---|---|
| `/签到` `/打卡` | 每日签到（随机积分/元宝二选一） |
| `/签到查询` `/查询签到` `/积分查询` `/余额查询` `/我的资产` | 查询本人资产；管理员可 `@成员` 查询他人 |
| `/兑换积分 N` | 兑换积分；管理员可 `@成员` 或追加 QQ 为他人兑换，N 为数量，支持 `@xx N` 与 `N @xx` 两种顺序 |
| `/兑换元宝 N` | 兑换元宝；规则同上 |
| `/签到排行 [月度|周排行]` | 查看签到天数排行（默认月度）；显示条数可配置 |
| `/签到重置 [@成员|QQ]` | 仅群管理员可用；重置指定成员（不指定默认自己） |

说明：
- 管理员查询/兑换他人时，支持 `@成员` 或直接写 QQ 号；未指定视为操作自己。
- 兑换指令的数额解析仅取文本中的“最后一个整数”为数量，避免误把时间等解析为数量。

---

### 配置项（_conf_schema.json）
- 奖励相关
  - `reward_points_min/max`：单次积分奖励范围（默认 10~50）
  - `reward_ingot_min/max`：单次元宝奖励范围（默认 5~30）
  - `reward_points_prob`：奖励积分的概率（0~1，默认 0.5）
- 权限与统计
  - `exchange_roles`：兑换权限模式（`admin_only`=仅管理员；`self_or_admin`=本人或管理员）
  - `storage_scope`：数据作用域（`group`=按群、`user`=按用户、`global`=全局），默认 `group`
  - `max_rank_list_size`：排行显示条数，默认 10
- 消息样式（可选）
  - `message_separator`：分隔线文本
  - `label_id`/`label_days`/`label_gain_points`/`label_gain_ingots`/`label_total_points`/`label_total_ingots`
  - 兑换成功模板：
    - `exchange_points_success_tpl`：占位符 `{amount}`、`{points}`
    - `exchange_ingots_success_tpl`：占位符 `{amount}`、`{ingots}`

示例：
```
exchange_points_success_tpl: "恭喜兑换成功 {amount} 积分，当前余额 {points}"
exchange_ingots_success_tpl: "恭喜兑换成功 {amount} 个元宝，剩余 {ingots} 个"
```

---

### 行为说明
- 签到奖励“积分/元宝”只选其一，不会同时赠与两种
- 连续签到、月/周签到天数自动维护；跨月/跨周自动归零对应统计
- 成员退群自动清空其在该群的数据；再次进群从零开始
- 管理员可用 `/签到重置 @成员` 对单人数据进行清空

---

### 常见问题
- 查询/兑换无响应：检查指令是否写对、插件是否启用、日志是否有报错
- 管理员权限判定：优先使用 `event.is_admin()`，兼容 OneBot 原始 `sender.role in {owner, admin}`
- 数据未更新：确认数据目录 `data/plugin-data/astrbot_plugin_qiandao/` 是否可写；或在 WebUI 重载插件

---

### 版本与作者
- name: `astrbot_plugin_qiandao`
- display_name: 签到/打卡（Napcat 风格）
- version: 1.0.1
- author: BvzRays

欢迎反馈与 PR！
