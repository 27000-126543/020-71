import requests
import json

BASE = "http://localhost:8000"

print("=" * 60)
print("1. 健康检查")
print("=" * 60)
r = requests.get(f"{BASE}/")
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print("\n" + "=" * 60)
print("2. 单条评论情绪研判 - 负面评论")
print("=" * 60)
r = requests.post(f"{BASE}/analyze", json={
    "comment_id": "c001",
    "post_id": "p001",
    "post_title": "产品质量讨论",
    "content": "这个产品太差了，简直是垃圾废物，我要维权投诉",
    "author_id": "u001",
    "author_name": "用户A",
    "scene": "default"
})
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print("\n" + "=" * 60)
print("3. 单条评论情绪研判 - 正面评论")
print("=" * 60)
r = requests.post(f"{BASE}/analyze", json={
    "comment_id": "c002",
    "post_id": "p001",
    "post_title": "产品质量讨论",
    "content": "这个产品不错，推荐给大家，很满意",
    "author_id": "u002",
    "author_name": "用户B",
    "scene": "default"
})
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print("\n" + "=" * 60)
print("4. 单条评论情绪研判 - 人身攻击")
print("=" * 60)
r = requests.post(f"{BASE}/analyze", json={
    "comment_id": "c003",
    "post_id": "p001",
    "post_title": "产品质量讨论",
    "content": "你们这些白痴蠢货，都是废物，滚出去！",
    "author_id": "u003",
    "author_name": "用户C",
    "scene": "default"
})
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print("\n" + "=" * 60)
print("5. 单条评论情绪研判 - 品牌抵制")
print("=" * 60)
r = requests.post(f"{BASE}/analyze", json={
    "comment_id": "c004",
    "post_id": "p001",
    "post_title": "产品质量讨论",
    "content": "抵制这个品牌！黑心企业割韭菜，再也不买了！",
    "author_id": "u004",
    "author_name": "用户D",
    "scene": "default"
})
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print("\n" + "=" * 60)
print("6. 创建规则配置")
print("=" * 60)
r = requests.post(f"{BASE}/rules/", json={
    "scene": "strict",
    "observe_threshold": 0.3,
    "review_threshold": 0.5,
    "block_threshold": 0.8,
    "negative_consecutive_count": 2,
    "negative_consecutive_window_minutes": 15
})
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print("\n" + "=" * 60)
print("7. 查询全部规则配置")
print("=" * 60)
r = requests.get(f"{BASE}/rules/")
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print("\n" + "=" * 60)
print("8. 批量回查 - 帖子情绪趋势")
print("=" * 60)
r = requests.get(f"{BASE}/batch/review/p001")
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print("\n" + "=" * 60)
print("9. 通知检查")
print("=" * 60)
r = requests.post(f"{BASE}/notifications/check/p001?scene=default")
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print("\n" + "=" * 60)
print("10. 查询评论分析结果")
print("=" * 60)
r = requests.get(f"{BASE}/result/c001")
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print("\n所有测试完成！")
