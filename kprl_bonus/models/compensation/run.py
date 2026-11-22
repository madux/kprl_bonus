"""Run-level shared rules (pure Python, no Odoo imports, no ORM, no env).

Applies AFTER the independent OPS / SALES legs: the legs never depend on
each other, and the shared budget cap + proration live only here.

Input:  list of per-employee leg outputs (frozen preview payloads):
            {"employee_id": int, "ops_gross": float|None,
             "sales_gross": float|None, "status": "calculated"|"blocked",
             "ops_deferred": float|None, "sales_deferred": float|None}
        plus run context:
            {"ebitda_cap_amount": float|None,   # run-level shared cap
             "effective_ops_pool": float|None} # informational only
Output: {"lines": [{... per-line finals ...}], "totals": {...}}

Rules:
- blocked lines pass through with None finals (missing is never zero).
- combined = (ops or 0) + (sales or 0) over calculated legs only.
- if ebitda_cap_amount is set and combined > cap:
      proration = cap / combined  (shared across BOTH legs equally)
  else proration = 1.0.
- net_payable = combined * proration; deferred amounts prorate equally.
- cap_pressure flag when combined > cap.
"""
from copy import deepcopy


def apply_run_rules(legs, ctx=None):
    ctx = dict(ctx or {})
    cap = ctx.get("ebitda_cap_amount")
    out_lines = []
    combined = 0.0
    for leg in legs:
        leg = dict(leg)
        if leg.get("status") == "blocked":
            out_lines.append({
                "employee_id": leg.get("employee_id"),
                "status": "blocked",
                "ops_gross": leg.get("ops_gross"),
                "sales_gross": leg.get("sales_gross"),
                "combined_gross": None,
                "proration": None,
                "net_payable": None,
                "deferred": None,
                "cap_adjustment": None,
            })
            continue
        ops = leg.get("ops_gross") or 0.0
        sales = leg.get("sales_gross") or 0.0
        gross = ops + sales
        combined += gross
        out_lines.append({
            "employee_id": leg.get("employee_id"),
            "status": "calculated",
            "ops_gross": ops,
            "sales_gross": sales,
            "combined_gross": gross,
            "proration": 1.0,
            "net_payable": gross,
            "deferred": (leg.get("ops_deferred") or 0.0) + (leg.get("sales_deferred") or 0.0),
            "cap_adjustment": 0.0,
        })
    cap_pressure = bool(cap is not None and combined > cap)
    proration = (cap / combined) if (cap_pressure and combined) else 1.0
    total_net = 0.0
    total_deferred = 0.0
    for line in out_lines:
        if line["status"] != "calculated":
            continue
        line["proration"] = proration
        line["cap_adjustment"] = line["combined_gross"] * (1.0 - proration)
        line["net_payable"] = line["combined_gross"] * proration
        line["deferred"] = line["deferred"] * proration
        total_net += line["net_payable"]
        total_deferred += line["deferred"]
    return {
        "lines": out_lines,
        "totals": {
            "employee_count": len(out_lines),
            "calculated_count": sum(1 for l in out_lines if l["status"] == "calculated"),
            "blocked_count": sum(1 for l in out_lines if l["status"] == "blocked"),
            "combined_gross": combined,
            "ebitda_cap_amount": cap,
            "cap_pressure": cap_pressure,
            "proration": proration,
            "total_net_payable": total_net,
            "total_deferred": total_deferred,
        },
    }
