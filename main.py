from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp

import os
import json
import random
import datetime
from typing import Dict, Any, Tuple


PLUGIN_ID = "astrbot_plugin_qiandao"
# 新的数据目录：data/plugin-data/astrbot_plugin_qiandao
DATA_DIR = os.path.join("data", "plugin-data", PLUGIN_ID)
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "checkin_data.json")
# 兼容旧目录：data/plugins/astrbot_plugin_qiandao
LEGACY_DATA_DIR = os.path.join("data", "plugins", PLUGIN_ID)
LEGACY_DATA_FILE = os.path.join(LEGACY_DATA_DIR, "checkin_data.json")


def _load_data() -> Dict[str, Any]:
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        # 兼容旧路径，若存在则读取并迁移
        if os.path.exists(LEGACY_DATA_FILE):
            with open(LEGACY_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 立即保存到新路径
            _save_data(data)
            return data
        return {}
    except Exception as e:
        logger.error(f"加载签到数据失败: {e}")
        return {}


def _save_data(data: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存签到数据失败: {e}")


def _today() -> datetime.date:
    return datetime.date.today()


def _year_week(date: datetime.date) -> Tuple[int, int]:
    iso_year, iso_week, _ = date.isocalendar()
    return iso_year, iso_week


def _get_ctx_id(event: AstrMessageEvent, cfg: Dict[str, Any]) -> str:
    # 可配置的数据作用域：group/user/global
    try:
        scope = (cfg.get("storage_scope") or "group").lower()
        platform = event.get_platform_name()
        if scope == "global":
            return f"{platform}:GLOBAL"
        if scope == "user":
            key = event.get_sender_id()
            return f"{platform}:U:{key}"
        # default group
        key = event.get_group_id() or event.get_session_id() or "default"
        return f"{platform}:G:{key}"
    except Exception:
        return "default"


def _default_user(user_id: str, username: str) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "username": username,
        "total_days": 0,
        "month_days": 0,
        "week_days": 0,
        "points": 0,
        "ingots": 0,
        "month_tag": "",       # YYYY-MM
        "week_tag": "",        # YYYY-WW
        "last_checkin": "",    # YYYY-MM-DD
    }


def _choose_reward(cfg: Dict[str, Any]) -> Tuple[str, int]:
    # 返回 (reward_type, amount) 其中 reward_type in {"points", "ingots"}
    points_prob = float(cfg.get("reward_points_prob", 0.5))
    if random.random() < points_prob:
        amt = random.randint(int(cfg.get("reward_points_min", 10)), int(cfg.get("reward_points_max", 50)))
        return "points", max(1, amt)
    amt = random.randint(int(cfg.get("reward_ingot_min", 5)), int(cfg.get("reward_ingot_max", 30)))
    return "ingots", max(1, amt)


@register("astrbot_plugin_qiandao", "bvzrays", "简单的签到插件", "1.0.1")
class NapcatCheckin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.data: Dict[str, Any] = _load_data()
        # 允许无配置运行；当存在 _conf_schema.json 时，AstrBot 会传入 AstrBotConfig
        # 保留原始对象以便动态读取（WebUI 修改后无需重启）
        self._cfg_obj = config
        self._cfg_cache: Dict[str, Any] = dict(config or {})

    def _curr_cfg(self) -> Dict[str, Any]:
        # 优先返回实时的 AstrBotConfig（兼容 dict 接口）；否则退回缓存
        try:
            if self._cfg_obj is not None:
                # AstrBotConfig 继承自 Dict，直接返回即可
                return self._cfg_obj
        except Exception:
            pass
        return self._cfg_cache

    def _is_group_admin(self, event: AstrMessageEvent) -> bool:
        # 优先用 AstrBot 封装判定
        try:
            if event.is_admin():
                return True
        except Exception:
            pass
        # 兼容 OneBot v11：从 raw_message.sender.role 读取
        try:
            raw = event.message_obj.raw_message
            if isinstance(raw, dict):
                sender = raw.get("sender", {}) or {}
                role = str(sender.get("role", "")).lower()
                if role in {"owner", "admin"}:
                    return True
        except Exception:
            pass
        return False

    def _get_user_bucket(self, event: AstrMessageEvent) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        ctx_id = _get_ctx_id(event, self._curr_cfg())
        user_id = event.get_sender_id()
        username = event.get_sender_name()
        bucket = self.data.setdefault(ctx_id, {})
        info = bucket.setdefault(user_id, _default_user(user_id, username))
        # 名称更新
        info["username"] = username
        return bucket, info

    def _get_group_ctx_bucket(self, event: AstrMessageEvent) -> Dict[str, Any]:
        """获取当前群维度的 bucket（用于管理员重置与退群事件），不受 storage_scope=user/global 影响。"""
        try:
            platform = event.get_platform_name()
            gid = event.get_group_id() or event.get_session_id() or "default"
            ctx_id = f"{platform}:G:{gid}"
            return self.data.setdefault(ctx_id, {})
        except Exception:
            return self.data.setdefault("default", {})

    def _roll_counters(self, info: Dict[str, Any], today: datetime.date) -> None:
        month_tag = today.strftime("%Y-%m")
        week_tag = f"{_year_week(today)[0]}-{_year_week(today)[1]:02d}"
        if info.get("month_tag") != month_tag:
            info["month_tag"] = month_tag
            info["month_days"] = 0
        if info.get("week_tag") != week_tag:
            info["week_tag"] = week_tag
            info["week_days"] = 0

    @filter.command("签到", alias={"打卡"})
    async def checkin(self, event: AstrMessageEvent):
        try:
            bucket, info = self._get_user_bucket(event)
            today = _today()
            self._roll_counters(info, today)

            if info.get("last_checkin") == today.isoformat():
                yield event.plain_result("今日已签到，请勿重复~")
                return

            # 随机奖励 二选一（使用实时配置）
            reward_type, reward_amt = _choose_reward(self._curr_cfg())

            info["total_days"] += 1
            info["month_days"] += 1
            info["week_days"] += 1
            if reward_type == "points":
                info["points"] += reward_amt
            else:
                info["ingots"] += reward_amt
            info["last_checkin"] = today.isoformat()

            _save_data(self.data)

            # 生成消息链（@并输出要求格式）
            cfg = self._curr_cfg()

            at = Comp.At(qq=event.get_sender_id())
            sep = str(cfg.get("message_separator", "-------------------------"))
            label_id = str(cfg.get("label_id", "●签到号码："))
            label_days = str(cfg.get("label_days", "●签到天数："))
            label_gain_points = str(cfg.get("label_gain_points", "●获得积分："))
            label_gain_ingots = str(cfg.get("label_gain_ingots", "●获得元宝："))
            label_total_points = str(cfg.get("label_total_points", "●积分数量："))
            label_total_ingots = str(cfg.get("label_total_ingots", "●元宝数量："))

            lines = []
            lines.append(sep)
            lines.append(f"{label_id}{event.get_sender_id()}")
            lines.append(f"{label_days}{info['total_days']}天")
            if reward_type == "points":
                lines.append(f"{label_gain_points}{reward_amt}积分")
            else:
                lines.append(f"{label_gain_ingots}{reward_amt}元宝")
            lines.append(f"{label_total_points}{info['points']}积分")
            lines.append(f"{label_total_ingots}{info['ingots']}元宝")
            lines.append(sep)

            body = "\n".join(lines)
            # 美化首行：@用户名 + 成功徽标
            yield event.chain_result([at, Comp.Plain(" ，✅ 签到成功\n" + body)])
        except Exception as e:
            logger.error(f"签到失败: {e}")
            yield event.plain_result("签到出现异常，请稍后再试")

    def _parse_exchange_args(self, event: AstrMessageEvent) -> Tuple[int, str]:
        """从消息中解析兑换数量与目标用户（@优先，其次纯数字QQ）。
        返回 (amount, target_uid or "")，amount<=0 代表未解析到。
        """
        amount = 0
        target_uid = ""
        # 提取 @
        try:
            for comp in event.get_messages():
                if isinstance(comp, Comp.At) and getattr(comp, "qq", None):
                    target_uid = str(comp.qq)
                    break
        except Exception:
            pass
        # 提取数字（数量 或 可能的 QQ）
        try:
            texts = []
            for comp in event.get_messages():
                if isinstance(comp, Comp.Plain):
                    texts.append(comp.text)
            texts.append(event.message_str or "")
            joined = " ".join(texts)
            # 取所有整数样式数字
            nums = []
            cur = ""
            for ch in joined:
                if ch.isdigit():
                    cur += ch
                else:
                    if cur:
                        nums.append(cur)
                        cur = ""
            if cur:
                nums.append(cur)
            # 选择一个作为数量：优先长度较小的数值（避免把QQ当数量）
            cand = sorted((int(n) for n in nums if n.isdigit()), key=lambda x: (len(str(x)), x))
            if cand:
                amount = cand[0]
            # 若未识别到 @，且存在看似QQ的长数字（>=5位），取其作为目标
            if not target_uid:
                qq_cands = [n for n in nums if n.isdigit() and len(n) >= 5]
                if qq_cands:
                    # 取第一个较长数字作为 QQ
                    target_uid = qq_cands[0]
        except Exception:
            pass
        return amount, target_uid

    @filter.command("兑换积分")
    async def exchange_points(self, event: AstrMessageEvent):
        try:
            role_mode = str(self._curr_cfg().get("exchange_roles", "self_or_admin"))
            is_admin = self._is_group_admin(event)
            amount, target_uid = self._parse_exchange_args(event)
            if amount <= 0:
                yield event.plain_result("兑换数量需为正整数")
                return

            # 目标用户：管理员可为他人；非管理员仅能为自己
            if role_mode == "admin_only":
                if not is_admin:
                    yield event.plain_result("仅管理员可执行积分兑换")
                    return
                # 管理员：无 @ 则默认自己
                target_uid = target_uid or event.get_sender_id()
                bucket = self._get_group_ctx_bucket(event)
                info = bucket.setdefault(target_uid, _default_user(target_uid, ""))
            else:  # self_or_admin 或 anyone
                if not is_admin:
                    # 非管理员：强制为自己
                    target_uid = event.get_sender_id()
                    _, info = self._get_user_bucket(event)
                else:
                    # 管理员：允许指定他人
                    if target_uid and target_uid != event.get_sender_id():
                        bucket = self._get_group_ctx_bucket(event)
                        info = bucket.setdefault(target_uid, _default_user(target_uid, ""))
                    else:
                        _, info = self._get_user_bucket(event)

            if info["points"] < amount:
                yield event.plain_result("积分不足，无法兑换")
                return
            info["points"] -= amount
            _save_data(self.data)
            tpl = str(self._curr_cfg().get("exchange_points_success_tpl", "已兑换积分 {amount}，剩余积分：{points}"))
            yield event.plain_result(tpl.format(amount=amount, points=info['points']))
        except Exception as e:
            logger.error(f"兑换积分失败: {e}")
            yield event.plain_result("兑换失败，请稍后再试")

    @filter.command("兑换元宝")
    async def exchange_ingots(self, event: AstrMessageEvent):
        try:
            role_mode = str(self._curr_cfg().get("exchange_roles", "self_or_admin"))
            is_admin = self._is_group_admin(event)
            amount, target_uid = self._parse_exchange_args(event)
            if amount <= 0:
                yield event.plain_result("兑换数量需为正整数")
                return

            if role_mode == "admin_only":
                if not is_admin:
                    yield event.plain_result("仅管理员可执行元宝兑换")
                    return
                target_uid = target_uid or event.get_sender_id()
                bucket = self._get_group_ctx_bucket(event)
                info = bucket.setdefault(target_uid, _default_user(target_uid, ""))
            else:
                if not is_admin:
                    target_uid = event.get_sender_id()
                    _, info = self._get_user_bucket(event)
                else:
                    if target_uid and target_uid != event.get_sender_id():
                        bucket = self._get_group_ctx_bucket(event)
                        info = bucket.setdefault(target_uid, _default_user(target_uid, ""))
                    else:
                        _, info = self._get_user_bucket(event)

            if info["ingots"] < amount:
                yield event.plain_result("元宝不足，无法兑换")
                return
            info["ingots"] -= amount
            _save_data(self.data)
            tpl = str(self._curr_cfg().get("exchange_ingots_success_tpl", "已兑换元宝 {amount}，剩余元宝：{ingots}"))
            yield event.plain_result(tpl.format(amount=amount, ingots=info['ingots']))
        except Exception as e:
            logger.error(f"兑换元宝失败: {e}")
            yield event.plain_result("兑换失败，请稍后再试")

    @filter.command("签到排行")
    async def rank(self, event: AstrMessageEvent, 类型: str = "月度"):
        try:
            ctx_id = _get_ctx_id(event, self._curr_cfg())
            bucket = self.data.get(ctx_id, {})
            if not bucket:
                yield event.plain_result("暂无签到数据")
                return

            flag = (类型 or "月度").strip()
            if "周" in flag:
                key = "week_days"
                title = "周排行（按签到天数）"
            else:
                key = "month_days"
                title = "月度排行（按签到天数）"

            # 按天数排行，前10
            max_n = int(self._curr_cfg().get("max_rank_list_size", 10))
            ranked = sorted(bucket.values(), key=lambda x: x.get(key, 0), reverse=True)[:max(1, max_n)]
            lines = [f"{title}"]
            for i, r in enumerate(ranked, 1):
                uname = r.get("username") or r.get("user_id")
                lines.append(f"{i}. {uname} - {r.get(key, 0)}天")
            yield event.plain_result("\n".join(lines))
        except Exception as e:
            logger.error(f"排行失败: {e}")
            yield event.plain_result("排行生成失败，请稍后再试")

    @filter.command("签到重置")
    async def reset_self(self, event: AstrMessageEvent, 目标: str = ""):
        try:
            # 仅群管理员可用
            if not self._is_group_admin(event):
                yield event.plain_result("仅群管理员可执行此操作")
                return

            # 识别重置对象：优先从 @ 提取，其次解析参数为 QQ
            target_uid = None
            try:
                for comp in event.get_messages():
                    if isinstance(comp, Comp.At) and comp.qq:
                        target_uid = str(comp.qq)
                        break
            except Exception:
                pass

            if not target_uid and 目标:
                # 去除非数字字符，尝试作为 QQ 号
                digits = ''.join(ch for ch in str(目标) if ch.isdigit())
                if digits:
                    target_uid = digits

            # 默认目标为自己
            if not target_uid:
                target_uid = event.get_sender_id()

            bucket = self._get_group_ctx_bucket(event)
            if target_uid in bucket:
                username = bucket[target_uid].get("username", "")
                bucket[target_uid] = _default_user(target_uid, username)
                _save_data(self.data)
                yield event.plain_result(f"已重置成员 {username or target_uid} 的签到数据")
                return
            yield event.plain_result("未找到该成员的签到数据")
        except Exception as e:
            logger.error(f"重置失败: {e}")
            yield event.plain_result("重置失败，请稍后再试")

    @filter.command("签到查询", alias={"查询签到", "余额查询", "积分查询", "我的资产"})
    async def query_assets(self, event: AstrMessageEvent):
        try:
            _, info = self._get_user_bucket(event)
            sep = str(self._curr_cfg().get("message_separator", "-------------------------"))
            lines = [
                "📊 签到资产",
                sep,
                f"💎 当前积分：{info['points']}",
                f"🪙 当前元宝：{info['ingots']}",
                f"📅 累计签到：{info['total_days']}天",
                f"🗓️ 本月签到：{info['month_days']}天",
                f"📆 本周签到：{info['week_days']}天",
                sep,
            ]
            yield event.plain_result("\n".join(lines))
        except Exception as e:
            logger.error(f"查询资产失败: {e}")
            yield event.plain_result("查询失败，请稍后再试")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def _auto_reset_on_leave(self, event: AstrMessageEvent):
        """监听群成员退群，自动重置其在该群的数据（兼容 OneBot v11 风格 notice）。"""
        try:
            raw = None
            try:
                raw = event.message_obj.raw_message
            except Exception:
                return

            # 仅处理 dict 风格的 notice
            if not isinstance(raw, dict):
                return

            post_type = str(raw.get("post_type", ""))
            notice_type = str(raw.get("notice_type", raw.get("event", "")))
            if post_type != "notice":
                # 兼容部分实现直接放在 event 字段
                if not ("decrease" in notice_type or "member_decrease" in notice_type):
                    return
            if not ("decrease" in notice_type or "member_decrease" in notice_type):
                return

            gid = str(raw.get("group_id", event.get_group_id() or ""))
            uid = str(raw.get("user_id", ""))
            if not gid or not uid:
                return

            # 使用群维度 bucket 重置该成员
            platform = event.get_platform_name()
            ctx_id = f"{platform}:G:{gid}"
            bucket = self.data.get(ctx_id, {})
            if uid in bucket:
                username = bucket[uid].get("username", "")
                bucket[uid] = _default_user(uid, username)
                _save_data(self.data)
        except Exception:
            # 忽略所有异常，避免影响其它流程
            pass

    async def terminate(self):
        pass


