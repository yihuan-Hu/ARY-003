"""
Checkpoint 1 Demo 脚本（角色 4 交付）

演示完整参赛事实链：
  User → 创建 Race → User 提交 Registration
  → Organizer 审核 Registration → Registration approved
  → 系统自动且幂等生成唯一 RaceProject
  → Rider 可读取自己的 Registration 和 RaceProject

用法：
  cd backend
  python demo.py

输出：每一步的请求/响应和 PASS/FAIL 判定。
"""
import json
import sys
import os

# 确保可以从 backend/ 运行
sys.path.insert(0, os.path.dirname(__file__))

# Windows GBK 控制台适配：强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app import create_app
from app.config import TestConfig
from app.database import reset_db


SEP = "=" * 60
SUB = "-" * 40


def main():
    # ---- 初始化 ----
    app = create_app(TestConfig)
    reset_db(app)
    client = app.test_client()

    print(SEP)
    print("ARY MVP Checkpoint 1 — 最小参赛事实链 Demo")
    print("角色 4：RaceProject API + 兼容适配 + Demo")
    print(SEP)

    passed = 0
    failed = 0

    def check(step, resp, expected_status, label=""):
        nonlocal passed, failed
        if isinstance(expected_status, (tuple, list)):
            ok = resp.status_code in expected_status
        else:
            ok = resp.status_code == expected_status
        status = "[PASS]" if ok else f"[FAIL] (expected {expected_status}, got {resp.status_code})"
        print(f"\n{SUB}")
        print(f"[{status}] Step {step}: {label}")
        print(f"  Status: {resp.status_code}")
        try:
            body = json.loads(resp.data)
            print(f"  Response: {json.dumps(body, indent=2, ensure_ascii=False)}")
        except Exception:
            print(f"  Response: {resp.data[:200]}")
        if ok:
            passed += 1
        else:
            failed += 1
        return json.loads(resp.data) if ok else None

    # ========================================
    # Step 0: 数据库初始化
    # ========================================
    print(f"\n{SEP}")
    print("[0] 数据库初始化")
    print(SEP)
    with app.app_context():
        from app.database import get_db
        db = get_db()
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        print(f"  已有表: {table_names}")
        assert "registrations" in table_names, "registrations 表不存在"
        assert "race_projects" in table_names, "race_projects 表不存在"
        print("  [OK] 新表 registrations / race_projects 已落库")

    # ========================================
    # Step 1: Organizer 登录
    # ========================================
    print(f"\n{SEP}")
    print("[1] Organizer 登录并创建 Race")
    print(SEP)

    # 创建 Organizer 和 Rider 用户
    with app.app_context():
        from app.database import get_db
        from app.utils.auth import hash_password
        db = get_db()
        # Organizer A
        db.execute(
            "INSERT INTO users (username, password_hash, roles) VALUES (?, ?, ?)",
            ("demo_org", hash_password("demo123"), json.dumps(["organizer"])),
        )
        # Rider A
        db.execute(
            "INSERT INTO users (username, password_hash, roles) VALUES (?, ?, ?)",
            ("demo_rider_a", hash_password("demo123"), json.dumps(["contestant"])),
        )
        # Rider B
        db.execute(
            "INSERT INTO users (username, password_hash, roles) VALUES (?, ?, ?)",
            ("demo_rider_b", hash_password("demo123"), json.dumps(["contestant"])),
        )
        # Organizer B (用于越权测试)
        db.execute(
            "INSERT INTO users (username, password_hash, roles) VALUES (?, ?, ?)",
            ("demo_org_b", hash_password("demo123"), json.dumps(["organizer"])),
        )
        db.commit()
    print("  [OK] 已创建: demo_org, demo_org_b, demo_rider_a, demo_rider_b")

    # Organizer A 登录
    org_login = client.post("/api/v1/auth/login",
                            data=json.dumps({"username": "demo_org", "password": "demo123"}),
                            content_type="application/json")
    data = check("1.1", org_login, 200, "Organizer 登录")
    org_token = data["data"]["token"]
    print(f"  Organizer token: {org_token[:20]}...")

    # Organizer B 登录
    org_b_login = client.post("/api/v1/auth/login",
                              data=json.dumps({"username": "demo_org_b", "password": "demo123"}),
                              content_type="application/json")
    org_b_token = json.loads(org_b_login.data)["data"]["token"]

    # Rider A 登录
    rider_a_login = client.post("/api/v1/auth/login",
                                data=json.dumps({"username": "demo_rider_a", "password": "demo123"}),
                                content_type="application/json")
    rider_a_token = json.loads(rider_a_login.data)["data"]["token"]

    # Rider B 登录
    rider_b_login = client.post("/api/v1/auth/login",
                                data=json.dumps({"username": "demo_rider_b", "password": "demo123"}),
                                content_type="application/json")
    rider_b_token = json.loads(rider_b_login.data)["data"]["token"]

    # ========================================
    # Step 2: Organizer 创建 Race
    # ========================================
    create_race = client.post("/api/v1/organizer/races",
                              data=json.dumps({"name": "ARY Demo Race", "status": "open"}),
                              content_type="application/json",
                              headers={"Authorization": f"Bearer {org_token}"})
    data = check("2", create_race, 201, "Organizer 创建 Race")
    race = data["data"]
    race_id = race["id"]
    print(f"  Race ID: {race_id}, Status: {race['status']}")

    # ========================================
    # Step 3: Rider A 提交 Registration
    # ========================================
    print(f"\n{SEP}")
    print("[3] Rider A 提交报名")
    print(SEP)

    submit = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    data = check("3.1", submit, 201, "Rider A 提交 Registration")
    reg_id = data["data"]["id"]
    print(f"  Registration ID: {reg_id}, Status: {data['data']['status']}")

    # 重复报名测试
    dup = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    check("3.2", dup, 409, "重复报名应返回 409 Conflict")

    # ========================================
    # Step 4: Rider 查看自己的 Registration
    # ========================================
    print(f"\n{SEP}")
    print("[4] Rider A 查看自己的 Registration")
    print(SEP)

    my_reg = client.get(
        f"/api/v1/rider/registrations/{reg_id}",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    check("4.1", my_reg, 200, "Rider A 查看自己的 Registration")

    my_regs = client.get(
        "/api/v1/rider/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    check("4.2", my_regs, 200, "Rider A 查看报名列表")

    # ========================================
    # Step 5: Organizer 查看 managed race 的报名
    # ========================================
    print(f"\n{SEP}")
    print("[5] Organizer 查看 managed race 报名列表")
    print(SEP)

    org_regs = client.get(
        f"/api/v1/organizer/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {org_token}"}
    )
    check("5", org_regs, 200, "Organizer 查看 managed race Registrations")

    # ========================================
    # Step 6: Organizer approve → 自动生成 RaceProject
    # ========================================
    print(f"\n{SEP}")
    print("[6] Organizer approve → 自动且幂等生成 RaceProject")
    print(SEP)

    approve = client.post(
        f"/api/v1/organizer/registrations/{reg_id}/approve",
        headers={"Authorization": f"Bearer {org_token}"}
    )
    data = check("6.1", approve, 200, "Organizer approve Registration")
    rp = data["data"]["race_project"]
    rp_id = rp["id"]
    print(f"  RaceProject ID: {rp_id}")
    print(f"  aggregate_ingestion_status: {rp['aggregate_ingestion_status']}")
    print(f"  connection_health: {rp['connection_health']}")
    print(f"  ca_connections (占位): {rp.get('ca_connections', 'MISSING')}")
    print(f"  work (占位): {rp.get('work', 'MISSING')}")
    print(f"  idempotent: {data['data']['idempotent']}")
    assert data["data"]["idempotent"] is False, "首次 approve 应 idempotent=false"

    # ========================================
    # Step 7: Rider 查看自己的 RaceProject
    # ========================================
    print(f"\n{SEP}")
    print("[7] Rider A 查看自动生成的 RaceProject")
    print(SEP)

    my_rp = client.get(
        f"/api/v1/rider/race-projects/{rp_id}",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    check("7", my_rp, 200, "Rider A 查看自己的 RaceProject（含占位字段）")

    # ========================================
    # Step 8: 再次 approve → 幂等！
    # ========================================
    print(f"\n{SEP}")
    print("[8] 再次 approve → 幂等，不重复生成 RaceProject")
    print(SEP)

    approve2 = client.post(
        f"/api/v1/organizer/registrations/{reg_id}/approve",
        headers={"Authorization": f"Bearer {org_token}"}
    )
    data = check("8.1", approve2, 200, "重复 approve（幂等）")
    assert data["data"]["idempotent"] is True, "重复 approve 应 idempotent=true"
    assert data["data"]["race_project"]["id"] == rp_id, "应返回同一个 RaceProject"
    print(f"  [OK] 确认为同一个 RaceProject (id={rp_id})")

    # 数据库验证
    with app.app_context():
        from app.database import get_db
        db = get_db()
        cnt = db.execute(
            "SELECT COUNT(*) as c FROM race_projects WHERE registration_id = ?",
            (reg_id,)
        ).fetchone()
        assert cnt["c"] == 1, f"数据库中有 {cnt['c']} 个 RaceProject，期望 1"
        print(f"  [OK] 数据库验证：race_projects 表中仅 {cnt['c']} 条记录")

    # ========================================
    # Step 9: Organizer 查看 managed race 的 RaceProjects
    # ========================================
    print(f"\n{SEP}")
    print("[9] Organizer 查看 managed race 的 RaceProjects 列表")
    print(SEP)

    org_rps = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {org_token}"}
    )
    check("9", org_rps, 200, "Organizer 查看 managed race RaceProjects")

    # ========================================
    # Step 10: 越权测试
    # ========================================
    print(f"\n{SEP}")
    print("[10] 越权测试")
    print(SEP)

    # Rider B 不能查看 Rider A 的 Registration
    rider_b_view = client.get(
        f"/api/v1/rider/registrations/{reg_id}",
        headers={"Authorization": f"Bearer {rider_b_token}"}
    )
    check("10.1", rider_b_view, 404,
          "Rider B 无法枚举或查看 Rider A 的 Registration")

    # Rider B 不能查看 Rider A 的 RaceProject
    rider_b_rp = client.get(
        f"/api/v1/rider/race-projects/{rp_id}",
        headers={"Authorization": f"Bearer {rider_b_token}"}
    )
    check("10.2", rider_b_rp, 404,
          "Rider B 无法枚举或查看 Rider A 的 RaceProject")

    # Organizer B 不能审核 Organizer A 的 Race 的报名
    org_b_approve = client.post(
        f"/api/v1/organizer/registrations/{reg_id}/approve",
        headers={"Authorization": f"Bearer {org_b_token}"}
    )
    check("10.3", org_b_approve, 403,
          "Organizer B 无法审核不属于自己的 Race 的报名")

    # Organizer B 不能查看 Organizer A 的 Race 的 RaceProjects
    org_b_rps = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {org_b_token}"}
    )
    check("10.4", org_b_rps, 403,
          "Organizer B 无法查看他人的 RaceProjects")

    # Rider 不能手动创建 RaceProject
    rider_create_rp = client.post(
        "/api/v1/rider/race-projects",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    check("10.5", rider_create_rp, (404, 405),
          "Rider 没有创建 RaceProject 的路由")

    # Public 不能访问 Racer/Organizer 接口
    public_access = client.get(
        f"/api/v1/organizer/races/{race_id}/registrations"
    )
    check("10.6", public_access, 401,
          "未认证用户无法访问 Organizer 接口")

    # ========================================
    # Final
    # ========================================
    print(f"\n{SEP}")
    print("Demo 完成")
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    print(SEP)

    if failed > 0:
        print("\n[FAIL] 存在失败步骤，请检查！")
        sys.exit(1)
    else:
        print("\n[OK] 全部通过！Checkpoint 1 参赛事实链验证成功。")
        print("\n   主链已跑通：")
        print("   User → 创建 Race → User 提交 Registration")
        print("   → Organizer 审核 Registration → Registration approved")
        print("   → 系统自动且幂等生成唯一 RaceProject")
        print("   → Rider 可读取自己的 Registration 和 RaceProject")
        print("   → 越权全部被拒绝")


if __name__ == "__main__":
    main()
