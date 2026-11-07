"""2026-Q2 workbook import (dry-run by default, Excel wins on apply).

Run in odoo-bin shell (env is provided):
    odoo-bin shell -d DB < tools/import_workbook_q2.py              # dry run
    KPRL_IMPORT_MODE=apply odoo-bin shell -d DB < tools/import_workbook_q2.py

Env knobs:
    KPRL_IMPORT_MODE  dry (default) | apply
    KPRL_WORKBOOK     path to the v31 xlsx (default: sibling of custom/kprl)
    KPRL_BACKUP       backup JSON path (apply mode writes before-images)
    KPRL_PERIOD       period name (default 2026-Q2)

Dry run prints FILL (missing, to create), OVERWRITE (differs, Excel wins)
and MATCH rows and changes nothing. Apply mode writes a JSON backup first,
then upserts. Records present in-app but absent from Excel are left alone.
"""
import json
import os
import sys
import tempfile

try:
    TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    TOOLS_DIR = "C:/Program Files/Odoo 17.0.20260507/server/custom/kprl/kprl_bonus/tools"
sys.path.insert(0, TOOLS_DIR)

try:
    import workbook_q2_data as W
except ImportError:
    print("openpyxl is required: pip install openpyxl")
    raise SystemExit(2)

MODE = os.environ.get("KPRL_IMPORT_MODE", "dry").strip().lower()
PERIOD_NAME = os.environ.get("KPRL_PERIOD", "2026-Q2").strip()
WB = os.environ.get("KPRL_WORKBOOK", os.path.join(os.path.dirname(os.path.dirname(TOOLS_DIR)), "KPRL_Bonus_Calculator_v31_working1.xlsx"))
BACKUP = os.environ.get("KPRL_BACKUP", os.path.join(tempfile.gettempdir(), "kprl_q2_backup.json"))

FILL, OVERWRITE, MATCH, SKIP = [], [], [], []
BACKUP_ROWS = []


def same(old, new, tol=1e-6):
    if old is None and new is None:
        return True
    if old is None or new is None:
        return False
    if isinstance(new, bool) or isinstance(old, bool):
        return bool(old) == bool(new)
    if isinstance(new, (int, float)) and isinstance(old, (int, float)):
        return abs(float(old) - float(new)) <= tol
    return str(old) == str(new)


def note(kind, label, details=""):
    {"fill": FILL, "overwrite": OVERWRITE, "match": MATCH, "skip": SKIP}[kind].append((label, details))


def snap(model, rid, vals):
    BACKUP_ROWS.append({"model": model, "id": rid, "before": vals})


def upsert(model_name, domain, vals, label, tol=1e-6, create_extra=None):
    Model = env[model_name]
    rec = Model.search(domain, limit=1)
    clean = {k: v for k, v in vals.items() if v is not None}
    if not rec:
        note("fill", label, "create %s" % clean)
        if MODE == "apply":
            rec = Model.create(dict(clean, **(create_extra or {})))
        return rec, "fill"
    diffs = []
    before = {}
    for k, v in clean.items():
        old = rec[k]
        if hasattr(old, "ids"):
            old = old.id or False
        before[k] = old
        if not same(old, v, tol):
            diffs.append("%s: %r -> %r" % (k, old, v))
    if not diffs:
        note("match", label)
        return rec, "match"
    note("overwrite", label, "; ".join(diffs))
    if MODE == "apply":
        snap(model_name, rec.id, before)
        rec.write(clean)
    return rec, "overwrite"
def main():
    data = W.load_workbook_data(WB, PERIOD_NAME)
    print("workbook: %d employees, %d %s perf rows, %d skus" % (len(data["employees"]), len(data["perf"]), PERIOD_NAME, len(data["skus"])))
    Grade = env["kprl.grade"]
    Dept = env["kprl.department"]
    grades = {}
    for code in ("SENMGT", "TIER1", "TIER2", "TIER3", "LEAD1", "ALEAD", "ASMGR", "MGR", "SUP1", "SUP2", "JUNIOR", "HYGIENE"):
        g = Grade.search([("code", "=", code)], limit=1)
        if not g:
            note("skip", "grade " + code, "missing - seed data first")
        grades[code] = g
    depts = {}
    for e in data["employees"]:
        depts.setdefault(e["dept"], None)
    for e in data["dept_scores"]:
        depts.setdefault(e["dept"], None)
    aliases = {"QA/QC": ["Quality Assurance"], "Marketing Dept": ["Marketing"], "Inventory Dept": ["Inventory"]}
    for name in depts:
        d = Dept.search([("name", "=", name)], limit=1)
        if not d:
            for alias in aliases.get(name, []):
                d = Dept.search([("name", "=", alias)], limit=1)
                if d:
                    break
            if d:
                if MODE == "apply":
                    d.write({"name": name})
                    note("overwrite", "department " + name, "renamed to workbook name")
                else:
                    note("fill", "department " + name, "will rename on apply")
        if not d:
            note("skip", "department " + name, "missing - seed data first")
        depts[name] = d
    Terr = env["kprl.territory"]
    terrs = {}
    for e in data["employees"]:
        if e["territory"]:
            terrs.setdefault(e["territory"], None)
    terrs["NATIONAL"] = None
    for code in terrs:
        tgt = data["terr_targets"].get(code, {})
        tvals = {"name": code, "code": code}
        if tgt:
            tvals.update({"rsm_target": tgt.get("rsm"), "team_target": tgt.get("team"),
                            "target_source": "team" if tgt.get("source") == "team" else "rsm"})
        t, _ = upsert("kprl.territory", [("code", "=", code)], tvals, "territory " + code)
        if not t:
            t = Terr.search([("name", "=", code)], limit=1)
        terrs[code] = t
    sales_grade = Grade.search([("code", "=", "SALES")], limit=1)
    if not sales_grade and MODE == "apply":
        sub = env["kprl.subpool"].search([("code", "=", "SALES")], limit=1)
        sales_grade = Grade.create({"name": "Sales (Field Force)", "code": "SALES", "sequence": 200, "yp_points": 0.0, "skill_max": 0.0, "aip_eligible": False, "is_senior_mgmt_tier": False, "deferral_rate": 0.0, "subpool_id": sub.id if sub else False})
        note("fill", "grade SALES", "created zero-point role grade")
    elif not sales_grade:
        note("fill", "grade SALES", "to create")
    grades["SALES"] = sales_grade
    Emp = env["kprl.employee"]
    emps = {}
    for e in data["employees"]:
        # Canonical staff-ID form (KPRL/xxxx): workbook ships dashes.
        sid = str(e["staff_id"] or "").strip().upper().replace("-", "/")
        vals = {"name": e["name"], "staff_id": sid, "department_id": depts[e["dept"]].id if depts[e["dept"]] else False,
                "pool_type": e["pool"], "track": e["track"], "status": "active" if e["active"] else "inactive",
                "is_active": e["active"], "active": e["active"], "is_sales": e["pool"] == "SALES",
                "sales_role": e["sales_role"],
                "skill_premium_pts": float(e["skill"] or 0.0)}
        want_grade = False
        if e["grade_code"]:
            want_grade = grades[e["grade_code"]].id if grades.get(e["grade_code"]) else False
        existent = Emp.search(['|', ("staff_id", "=", e["staff_id"]), ("staff_id", "=", sid)], limit=1)
        if existent and existent.grade_id:
            cur = existent.grade_id
            cur_id = cur.id if hasattr(cur, "id") else cur
            cur_code = cur.code if hasattr(cur, "code") else cur
            if want_grade and cur_id != want_grade:
                note("skip", "grade " + e["staff_id"], "kept app grade %s vs excel %s" % (cur_code, e["grade_code"]))
        elif want_grade:
            vals["grade_id"] = want_grade
        if e["territory"]:
            vals["territory_id"] = terrs[e["territory"]].id if terrs[e["territory"]] else False
        rec, status = upsert("kprl.employee", ['|', ("staff_id", "=", e["staff_id"]), ("staff_id", "=", sid)], vals, "employee " + sid)
        emps[e["staff_id"]] = rec if (rec or status == "match") else False
    Period = env["kprl.bonus.period"]
    for q in data["quarters"]:
        if q["ebitda"] is None and q["kpi"] is None and q["nat_target"] is None:
            continue
        start, end = W.quarter_dates(q["name"])
        upsert("kprl.bonus.period", [("name", "=", q["name"])],
               {"name": q["name"], "date_start": start, "date_end": end,
                "ebitda_margin": float(q["ebitda"]) * 100.0 if q["ebitda"] is not None else None,
                "company_kpi": float(q["kpi"]) * 100.0 if q["kpi"] is not None else None,
                "national_sales_target": q["nat_target"],
                "national_retrieval_target": q["nat_retr_target"]},
               "period " + q["name"])
    period = Period.search([("name", "=", PERIOD_NAME)], limit=1)
    if not period and MODE == "apply":
        print("period record missing - create it first")
        raise SystemExit(3)
    pid = period.id if period else False
    for p in data["perf"]:
        emp = emps.get(p["staff_id"])
        if emp is None:
            note("skip", "perf " + p["staff_id"], "no employee")
            continue
        emp_id = emp.id if emp else False
        upsert("kprl.performance.input", [("period_id", "=", pid), ("employee_id", "=", emp_id)],
               {"period_id": pid, "employee_id": emp_id,
                "appraisal_score": p["appraisal"], "team_pct": p["behaviour"],
                "own_target": p["own_target"], "own_sales": p["own_sales"],
                "own_retrievals": p["own_retr"], "product_knowledge_score": p["pk"],
                "call_report_compliance": p["call"], "customer_coverage_rate": p["coverage"],
                "new_customer_acquisition": p["new"], "prod_know": p["pk"],
                "call_rep": p["call"], "coverage": p["coverage"],
                "new_cust": p["new"]},
               "perf %s %s" % (PERIOD_NAME, p["staff_id"]))
    Prod = env["kprl.product"]
    prods = {}
    for s in data["skus"]:
        rec, status = upsert("kprl.product", [("name", "=", s["name"])],
                        {"name": s["name"], "code": s["name"], "category": s["category"],
                         "unit_price": s["price"], "sku_rate": s["rate_pct"], "margin_pct": s["margin_pct"]},
                        "product " + s["name"])
        prods[s["name"]] = rec if (rec or status == "match") else False
    for s in data["skus"]:
        prod_id = prods[s["name"]].id if prods[s["name"]] else False
        upsert("kprl.product.pool", [("period_id", "=", pid), ("product_id", "=", prod_id)],
               {"period_id": pid, "product_id": prod_id,
                "quantity_units": s["units"], "unit_price": s["price"],
                "sku_rate": s["rate_pct"]},
               "pool %s %s" % (PERIOD_NAME, s["name"]))
    upsert("kprl.bonus.parameter", [("period_id", "=", pid)],
           dict({"period_id": pid}, **data["params"]), "params " + PERIOD_NAME)
    for d in data["dept_scores"]:
        dept = depts[d["dept"]]
        if not dept:
            continue
        upsert("kprl.dept.kpi.multiplier", [("period_id", "=", pid), ("department_id", "=", dept.id)],
               {"period_id": pid, "department_id": dept.id,
                "kpi_score": d["score"], "gmp_status": d["gmp"], "self_flag": d["selfrep"]},
               "deptkpi %s %s" % (PERIOD_NAME, d["dept"]))
    Teng = env["kprl.territory.engine"]
    eng = Teng.search([("period_id", "=", pid)], limit=1)
    if not eng:
        note("fill", "sales engine " + PERIOD_NAME, "create")
        if MODE == "apply":
            eng = Teng.create({"period_id": pid})
    Role = env["kprl.role.parameter"]
    roles = {}
    for key in ("gm", "nsm", "headtech", "rsm", "asm", "rsm_asm"):
        r = Role.search([("role", "=", key)], limit=1)
        if not r:
            note("skip", "role " + key, "missing - seed data first")
        roles[key] = r
    eng_id = eng.id if eng else False
    if eng or MODE == "dry":
        for key, share in W.ROLE_SHARES.items():
            if not roles[key]:
                continue
            upsert("kprl.role.share.lines",
                   [("role_share_line_id", "=", eng_id), ("role_id", "=", roles[key].id), ("period_id", "=", pid)],
                   {"role_share_line_id": eng_id, "period_id": pid, "role_id": roles[key].id,
                    "share_rate": share, "dual_factor": data["params"].get("rsm_asm_dual_factor") or 0.55},
                   "share %s %s" % (PERIOD_NAME, key))
        for key in ("SW1", "NORTH", "SW2", "SE/SS", "NATIONAL"):
            terr = terrs.get(key)
            if terr is None:
                continue
            terr_id = terr.id if terr else False
            upsert("sale.territory.config",
                   [("territory_engine_id", "=", eng_id), ("territory_id", "=", terr_id)],
                   {"territory_engine_id": eng_id, "territory_id": terr_id,
                    "accel_kick_in": data["params"].get("i1_accelerator_kick_in", 100.0) / 100.0,
                    "accel_max": data["params"].get("i2_accelerator_ceiling", 150.0) / 100.0,
                    "accel_boost": data["params"].get("i3_accelerator_boost", 50.0) / 100.0,
                    "cap_stretch": data["params"].get("i4_stretch_individual_cap") or 5000000.0,
                    "cap_indiv_max": data["params"].get("g_individual_quarterly_cap") or 2000000.0,
                    "lead_premium": data["params"].get("g_leadership_premium") or 1.10},
                   "terrconfig %s %s" % (PERIOD_NAME, key))
        for e in data["employees"]:
            if not (e["pool"] == "SALES" or e["track"] in ("sales", "both")):
                continue
            role = roles.get(e["sales_role"])
            if not role:
                note("skip", "engine line " + e["staff_id"], "no employee or role")
                continue
            terr = terrs.get(e["territory"] or "NATIONAL")
            line_emp = emps.get(e["staff_id"])
            line_emp_id = line_emp.id if line_emp else False
            perf_by_staff = {q["staff_id"]: q for q in data["perf"]}
            pq = perf_by_staff.get(e["staff_id"], {})
            line_vals = {"territory_engine_id": eng_id, "employee_id": line_emp_id,
                         "territory_id": terr.id if terr else False, "role_id": role.id,
                         "own_target": pq.get("own_target"), "own_sales": pq.get("own_sales"),
                         "own_retrival": pq.get("own_retr"), "product_knowledge_score": pq.get("pk"),
                         "call_report_compliance": pq.get("call"), "customer_coverage_rate": pq.get("coverage"),
                         "new_customer_acquisition": pq.get("new"), "prod_know": pq.get("pk"),
                         "call_rep": pq.get("call"), "coverage": pq.get("coverage"),
                         "new_cust": pq.get("new")}
            upsert("kprl.territory.engine.lines",
                   [("territory_engine_id", "=", eng_id), ("employee_id", "=", line_emp_id)],
                   line_vals,
                   "engline %s %s" % (PERIOD_NAME, e["staff_id"]))
    if MODE == "apply":
        with open(BACKUP, "w", encoding="utf-8") as fh:
            json.dump(BACKUP_ROWS, fh, indent=1, default=str)
        print("backup written: %s (%d rows)" % (BACKUP, len(BACKUP_ROWS)))
        env.cr.commit()
        print("transaction committed")
    print("MODE=%s FILL=%d OVERWRITE=%d MATCH=%d SKIP=%d" % (MODE, len(FILL), len(OVERWRITE), len(MATCH), len(SKIP)))
    for label, details in OVERWRITE:
        print("OVERWRITE %s :: %s" % (label, details))
    for label, details in SKIP:
        print("SKIP %s :: %s" % (label, details))
    if MODE == "dry":
        print("dry run - nothing written. Set KPRL_IMPORT_MODE=apply to import (Excel wins).")
    else:
        print("apply done. Next: run Bonus Engine action_compute for %s, then tools/validate_v30_odoo.py" % PERIOD_NAME)


main()
