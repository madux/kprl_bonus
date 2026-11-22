"""Sales engine tests (pure Python, no Odoo required)."""
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "models" / "compensation"))
import sales as S
from policy import PolicySnapshot
FAILS = []
def check(label, got, want, tol=1e-6):
    ok = abs(float(got) - want) <= tol if isinstance(want, float) else got == want
    print(("PASS " if ok else "FAIL ") + label + " got=%r want=%r" % (got, want))
    if not ok:
        FAILS.append(label)
pol = PolicySnapshot()
def asm_entry(**kw):
    d = {"role": "asm", "own_target": 100e6, "own_sales": 82e6, "own_retrieval": 74e6,
         "territory_sales": None, "territory_retrieval": None, "territory_target": None,
         "national_sales": None, "national_target": None, "national_retrieval": None,
         "product_knowledge": 0.8, "call_report": 0.9, "customer_coverage": 0.7,
         "new_customer": 0.6, "years_of_service": 4, "employee_id": 1, "territory_key": "SW2"}
    d.update(kw)
    return d
# role shares
check("asm share", S.role_share("asm", pol), 0.55)
check("rsm share", S.role_share("rsm", pol), 0.22)
check("dual share", S.role_share("rsm_asm", pol), (0.22 + 0.55) * 0.55)
check("gm share", S.role_share("gm", pol), 0.10)
# ASM full calc: attain 0.82 -> sales gate ramp (0.65->0.70) = 1.0
r = S.calculate_sales_payout(asm_entry(), pol)
check("asm attainment", r["sales_attainment"], 0.82)
check("asm sales gate", r["sales_gate"], 1.0)
check("asm retr rate", round(r["retrieval_rate"], 6), round(74e6 / 82e6, 6))
check("asm retr gate", r["retrieval_gate"], 1.0)
check("asm sales comm", r["sales_commission"], 82e6 * 0.55 * 0.003)
check("asm retr comm", r["retrieval_commission"], 74e6 * 0.55 * 0.007)
check("asm eligible", r["eligible_commission"], r["sales_commission"] + r["retrieval_commission"])
check("asm kpi", round(r["kpi_multiplier"], 6), round(0.80 + (0.8*0.4 + 0.9*0.1 + 0.7*0.3 + 0.6*0.2) * 0.40, 6))
check("asm accel none", r["accelerator"], 1.0)
check("asm normal cap", r["cap"], 2000000.0)
check("asm capped", r["final_payout"] <= 2000000.0, True)
# below-floor ASM: attainment 0.5 -> gate 0 -> eligible 0
r0 = S.calculate_sales_payout(asm_entry(own_sales=50e6, own_retrieval=40e6), pol)
check("subfloor gate", r0["sales_gate"], 0.0)
check("subfloor eligible", r0["eligible_commission"], 0.0)
check("subfloor final", r0["final_payout"], 0.0)
# ramp mid: attainment 0.675 on ASM floor 0.65/min 0.70 -> 0.5
rm = S.calculate_sales_payout(asm_entry(own_sales=67.5e6, own_retrieval=60e6), pol)
check("ramp gate half", rm["sales_gate"], 0.5)
# accelerator: 125% attainment -> 1.25, stretch cap
ra = S.calculate_sales_payout(asm_entry(own_sales=125e6, own_retrieval=110e6), pol)
check("accel 125", ra["accelerator"], 1.25)
check("stretch cap", ra["cap"], 5000000.0)
# RSM leadership floor via batch
entries = [asm_entry(employee_id=1, territory_key="SW2"),
           {"role": "rsm", "own_target": None, "own_sales": None, "own_retrieval": None,
            "territory_sales": 200e6, "territory_retrieval": 150e6, "territory_target": 250e6,
            "national_sales": None, "national_target": None, "national_retrieval": None,
            "product_knowledge": 0.7, "call_report": 0.7, "customer_coverage": 0.7,
            "new_customer": 0.7, "years_of_service": 9, "employee_id": 2, "territory_key": "SW2"}]
b = S.calculate_sales_batch(entries, pol)
rsm = [x for x in b if x["employee_id"] == 2][0]
check("rsm attainment", rsm["sales_attainment"], 0.8)
check("rsm gate full", rsm["sales_gate"], 1.0)
check("rsm leadership >0", rsm["leadership_floor"] > 0, True)
check("rsm floor formula", round(rsm["leadership_floor"], 2),
      round(1.0 * 1.20 * S.asm_sub_base(entries[0], pol), 2))
check("rsm final>=floor", rsm["final_payout"] >= min(rsm["leadership_floor"], rsm["cap"]), True)
territory = S.aggregate_territory_performance([
    {"own_target": 100e6, "own_sales": 80e6, "own_retrieval": 60e6},
    {"own_target": 50e6, "own_sales": 30e6, "own_retrieval": 24e6},
    {"own_target": None, "own_sales": 0.0, "own_retrieval": None},
])
check("territory sales sums staff actuals", territory["territory_sales"], 110e6)
check("territory retrieval sums staff actuals", territory["territory_retrieval"], 84e6)
check("team target sums staff targets", territory["team_target"], 150e6)
rolled_up_rsm = S.calculate_sales_payout({
    "role": "rsm",
    "territory_sales": territory["territory_sales"],
    "territory_retrieval": territory["territory_retrieval"],
    "territory_target": territory["team_target"],
    "product_knowledge": 0.8, "call_report": 0.8,
    "customer_coverage": 0.8, "new_customer": 0.8,
    "years_of_service": 4,
}, pol)
check("rsm attainment uses team totals", rolled_up_rsm["sales_attainment"], 110.0 / 150.0)
check("rsm retrieval rate uses team totals", rolled_up_rsm["retrieval_rate"], 84.0 / 110.0)
# missing target -> blocked, not zero
rb = S.calculate_sales_payout(asm_entry(own_target=None), pol)
check("missing blocked", rb["final_payout"], None)
check("missing reason", bool(rb.get("blocked_reason")), True)
# missing KPI -> blocked
rk = S.calculate_sales_payout(asm_entry(product_knowledge=None), pol)
check("kpi blocked", rk["final_payout"], None)
# zero target divisor -> blocked
rz = S.calculate_sales_payout(asm_entry(own_target=0), pol)
check("zero target blocked", rz["final_payout"], None)
# top-role national path
rg = S.calculate_sales_payout({"role": "gm", "own_target": None, "own_sales": None, "own_retrieval": None,
    "territory_sales": None, "territory_retrieval": None, "territory_target": None,
    "national_sales": 900e6, "national_target": 1000e6, "national_retrieval": 800e6,
    "product_knowledge": 0.9, "call_report": 0.9, "customer_coverage": 0.9,
    "new_customer": 0.9, "years_of_service": 12}, pol)
check("gm attainment", rg["sales_attainment"], 0.9)
check("gm gate", rg["sales_gate"], 1.0)
check("gm base", rg["commissionable_sales_base"], 900e6 * 0.10)
print("----")
if FAILS:
    print("FAILURES: %d" % len(FAILS))
    raise SystemExit(1)
print("ALL SALES CHECKS PASSED")
