import requests
import json
from datetime import datetime, timedelta

BASE = "http://localhost:8000"

def print_divider(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


print_divider("测试 1：高风险类别低分但命中关键词 → 至少人工复核")
# 只带一个"抵制"词，分数低，但命中 brand_boycott
r = requests.post(f"{BASE}/analyze", json={
    "comment_id": "t1_low_boycott",
    "post_id": "test_new",
    "post_title": "",
    "content": "抵制一下",
    "author_id": "u1",
    "author_name": "用户A",
    "scene": "default"
})
data = r.json()
print(f"内容: '抵制一下'")
print(f"  情绪: {data['emotion_label']} (强度 {data['intensity_score']})")
print(f"  建议动作: {data['action_label']} (should be 人工复核)")
assert data["suggested_action"] == "review", f"应为 review，实际 {data['suggested_action']}"
print("  ✓ 通过")

# 只带一个"维权"词
r = requests.post(f"{BASE}/analyze", json={
    "comment_id": "t1_low_rights",
    "post_id": "test_new",
    "post_title": "",
    "content": "大家要不要一起维权",
    "author_id": "u2",
    "author_name": "用户B",
    "scene": "default"
})
data = r.json()
print(f"内容: '大家要不要一起维权'")
print(f"  情绪: {data['emotion_label']} (强度 {data['intensity_score']})")
print(f"  建议动作: {data['action_label']} (should be 人工复核)")
assert data["suggested_action"] == "review", f"应为 review，实际 {data['suggested_action']}"
print("  ✓ 通过")

# 只带一个辱骂词
r = requests.post(f"{BASE}/analyze", json={
    "comment_id": "t1_low_attack",
    "post_id": "test_new",
    "post_title": "",
    "content": "你这个白痴",
    "author_id": "u3",
    "author_name": "用户C",
    "scene": "default"
})
data = r.json()
print(f"内容: '你这个白痴'")
print(f"  情绪: {data['emotion_label']} (强度 {data['intensity_score']})")
print(f"  建议动作: {data['action_label']} (should be 人工复核)")
assert data["suggested_action"] == "review", f"应为 review，实际 {data['suggested_action']}"
print("  ✓ 通过")

# 普通吐槽（仅 complaint 类）→ 观察
r = requests.post(f"{BASE}/analyze", json={
    "comment_id": "t1_complaint_only",
    "post_id": "test_new",
    "post_title": "",
    "content": "这个东西太差了有点失望",
    "author_id": "u4",
    "author_name": "用户D",
    "scene": "default"
})
data = r.json()
print(f"内容: '这个东西太差了有点失望' (普通吐槽)")
print(f"  情绪: {data['emotion_label']} (强度 {data['intensity_score']})")
print(f"  建议动作: {data['action_label']} (should be 观察)")
print(f"  风险类别: {[r['category'] for r in data['risk_reasons']]}")
assert data["suggested_action"] == "observe", f"应为 observe，实际 {data['suggested_action']}"
print("  ✓ 通过")


print_divider("测试 2：批量回查引爆评论按时间排序（最早的排前面）")
base_time = datetime.now()
# 先上传 3 条评论：轻度(0.5) → 中度(0.75) → 重度(1.0)
comments_for_batch = []
contents = [
    ("b2_earliest_mid", "这个产品有点差劲哦，用着不太舒服", 0, 0.50),   # 假设中度负面
    ("b2_middle_hot", "太垃圾了，简直是在骗钱！失望透顶！", 1, 0.85),     # 更高
    ("b2_latest_worst", "废物产品，我要维权投诉抵制这个品牌！！！", 2, 1.0),  # 最高
]
for cid, content, minute_offset, _ in contents:
    published = base_time - timedelta(minutes=30 - minute_offset * 5)
    comments_for_batch.append({
        "comment_id": cid,
        "post_id": "post_chain",
        "post_title": "某产品讨论",
        "content": content,
        "author_id": f"u{minute_offset}",
        "author_name": f"用户{minute_offset+1}",
        "published_at": published.isoformat(),
    })

r = requests.post(f"{BASE}/batch/submit", json={
    "scene": "default",
    "comments": comments_for_batch
})
print(f"批量提交 {r.json()['total']} 条")

# 查询回查
r = requests.get(f"{BASE}/batch/review/post_chain")
data = r.json()
print(f"\n引爆评论（应按时间升序，最早的排前面）:")
for idx, ic in enumerate(data["igniting_comments"]):
    print(f"  [{idx+1}] {ic['comment_id']} 时间={ic['published_at'][-8:]} 强度={ic['intensity_score']} 内容='{ic['content'][:30]}'")

# 验证顺序：按 published_at 升序
times = [ic["published_at"] for ic in data["igniting_comments"]]
assert times == sorted(times), f"引爆评论未按时间升序排列: {times}"
print("  ✓ 引爆评论已按发布时间升序排列")


print_divider("测试 3：通知预警 - 连续走高负面才触发，夹中性/下降不触发")
# 3a: 先造一个 3 条连续且强度上升的负面链
# 第一条：轻度负面（命中 complaint + 轻微个人攻击，强度 0.4~0.5）
# 第二条：中度负面（brand_boycott + complaint，强度 0.6~0.75）
# 第三条：重度负面（personal_attack + collective_rights + brand_boycott，强度 0.85+）
chain_comments = [
    ("n3a_1", "太差了，东西做得真的很差，失望透顶，差评！", 10, "default"),
    ("n3a_2", "太垃圾了，抵制这个品牌，再也不买了，黑心割韭菜！", 8, "default"),
    ("n3a_3", "垃圾废物白痴！我要投诉维权，大家一起抵制这个品牌！！！", 5, "default"),
]
for cid, content, min_offset, scene in chain_comments:
    published = datetime.now() - timedelta(minutes=min_offset)
    r = requests.post(f"{BASE}/analyze", json={
        "comment_id": cid,
        "post_id": "post_notify_chain",
        "post_title": "通知测试",
        "content": content,
        "author_id": cid,
        "author_name": cid,
        "published_at": published.isoformat(),
        "scene": scene,
    })
    d = r.json()
    print(f"  提交 {cid}: {d['emotion_label']} 强度={d['intensity_score']} 动作={d['action_label']}")

r = requests.post(f"{BASE}/notifications/check/post_notify_chain?scene=default")
data = r.json()
print(f"\n连续走高3条 → 触发预警? {data['alert_triggered']}")
print(f"  理由: {data.get('message')}")
print(f"  强度趋势: {data.get('intensity_trend', 'N/A')}")
assert data["alert_triggered"] == True, "连续走高3条负面应触发预警"
print("  ✓ 连续走高负面已触发预警")

# 3b: 中间夹一条中性 → 不触发
broken_comments = [
    ("n3b_1", "太差了，东西做得真的很差，失望透顶，差评！", 9, "default"),   # 轻度负面
    ("n3b_2", "还可以吧，我觉得还行，继续努力", 7, "default"),                  # 中性/正面，打断
    ("n3b_3", "垃圾废物白痴！我要投诉维权抵制！！！", 5, "default"),             # 重度负面
]
for cid, content, min_offset, scene in broken_comments:
    published = datetime.now() - timedelta(minutes=min_offset)
    r = requests.post(f"{BASE}/analyze", json={
        "comment_id": cid,
        "post_id": "post_notify_broken",
        "post_title": "通知测试2",
        "content": content,
        "author_id": cid,
        "author_name": cid,
        "published_at": published.isoformat(),
        "scene": scene,
    })
    d = r.json()
    print(f"  提交 {cid}: {d['emotion_label']} 强度={d['intensity_score']} 动作={d['action_label']}")

r = requests.post(f"{BASE}/notifications/check/post_notify_broken?scene=default")
data = r.json()
print(f"\n中间夹中性 → 触发预警? {data['alert_triggered']}")
print(f"  理由: {data.get('message')}")
assert data["alert_triggered"] == False, "中间夹中性评论不应触发预警"
print("  ✓ 中间夹中性/正面不会触发预警")

# 3c: 负面但强度下降 → 不触发
desc_comments = [
    ("n3c_1", "垃圾废物白痴！我要投诉维权，大家一起抵制！！！", 10, "default"),  # 高
    ("n3c_2", "太差了，东西做得真的很差，失望透顶，差评！", 8, "default"),         # 中
    ("n3c_3", "东西做得一般般有点差", 5, "default"),                                  # 低
]
for cid, content, min_offset, scene in desc_comments:
    published = datetime.now() - timedelta(minutes=min_offset)
    r = requests.post(f"{BASE}/analyze", json={
        "comment_id": cid,
        "post_id": "post_notify_desc",
        "post_title": "通知测试3",
        "content": content,
        "author_id": cid,
        "author_name": cid,
        "published_at": published.isoformat(),
        "scene": scene,
    })
    d = r.json()
    print(f"  提交 {cid}: {d['emotion_label']} 强度={d['intensity_score']} 动作={d['action_label']}")

r = requests.post(f"{BASE}/notifications/check/post_notify_desc?scene=default")
data = r.json()
print(f"\n强度下降 → 触发预警? {data['alert_triggered']}")
print(f"  理由: {data.get('message')}")
assert data["alert_triggered"] == False, "强度下降的负面链不应触发预警"
print("  ✓ 强度下降的负面链不会触发预警")


print_divider("测试 4：通知摘要包含连续评论链路（时间、作者、片段）")
print("查看测试 3a 返回的摘要内容和 rising_chain 字段...")
# 重新触发 3a 的通知（我们可以发新帖子再触发一次，但 3a 已返回过完整结果）
# 这里直接用上面已触发的结果做验证：rising_chain 应有 comment_id / published_at / author / intensity / content_snippet
# 由于我们无法直接读取上面的 summary，这里再制造一个新的链路来获得完整输出

fresh_comments = [
    ("n4_1", "太差了，东西做得真的很差，失望透顶，差评！", 12, "用户甲", "default"),
    ("n4_2", "太垃圾了，抵制这个品牌，再也不买了，黑心割韭菜！", 9, "用户乙", "default"),
    ("n4_3", "垃圾废物白痴！我要投诉维权，大家一起抵制这个品牌！！！", 6, "用户丙", "default"),
]
for cid, content, min_offset, author, scene in fresh_comments:
    published = datetime.now() - timedelta(minutes=min_offset)
    requests.post(f"{BASE}/analyze", json={
        "comment_id": cid,
        "post_id": "post_notify_detail",
        "post_title": "通知测试详情",
        "content": content,
        "author_id": cid,
        "author_name": author,
        "published_at": published.isoformat(),
        "scene": scene,
    })

r = requests.post(f"{BASE}/notifications/check/post_notify_detail?scene=default")
data = r.json()
print(f"触发预警: {data['alert_triggered']}")
print(f"\n摘要内容:\n{data['summary']}")
print(f"\nrising_chain 结构化数据:")
for idx, item in enumerate(data.get("rising_chain", [])):
    print(f"  [{idx+1}] comment_id={item['comment_id']}")
    print(f"       时间={item['published_at'][-8:]}")
    print(f"       作者={item['author_name']}")
    print(f"       强度={item['intensity_score']}")
    print(f"       片段='{item['content_snippet']}'")

# 验证链路完整
assert len(data.get("rising_chain", [])) >= 3, "rising_chain 至少包含 3 条"
for item in data["rising_chain"]:
    assert item["comment_id"], "缺少 comment_id"
    assert item["published_at"], "缺少 published_at"
    assert item["author_name"], "缺少 author_name"
    assert "content_snippet" in item, "缺少 content_snippet"
# 摘要里应包含"评论链路如下"
assert "评论链路如下" in data["summary"], "摘要中未包含评论链路描述"
print("\n  ✓ 通知摘要和 rising_chain 均包含时间、作者、片段")


print("\n" + "=" * 70)
print("  🎉 所有 4 项改动验证全部通过！")
print("=" * 70)
