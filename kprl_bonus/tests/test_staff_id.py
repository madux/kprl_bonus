"""Staff-ID canonical form tests (pure Python, no Odoo required)."""
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "models"))
import kprl_math as KM
FAILS = []
def check(label, got, want):
    ok = got == want
    print(("PASS " if ok else "FAIL ") + label + " got=%r want=%r" % (got, want))
    if not ok:
        FAILS.append(label)
def check_raises(label, fn):
    try:
        fn()
    except ValueError:
        print("PASS " + label + " raised ValueError")
        return
    print("FAIL " + label + " did not raise")
    FAILS.append(label)
check("dash to slash", KM.normalize_staff_id("KPRL-0057"), "KPRL/0057")
check("slash kept", KM.normalize_staff_id("KPRL/0057"), "KPRL/0057")
check("case+space", KM.normalize_staff_id("  kprl-001 "), "KPRL/001")
check("bare digits kept", KM.normalize_staff_id("181818"), "181818")
check("check slash", KM.check_staff_id("KPRL/0057"), "KPRL/0057")
check("check dash normalized", KM.check_staff_id("kprl-043"), "KPRL/043")
check("check bare digits", KM.check_staff_id("181818"), "181818")
for bad in ["N/A", "", "ABC-123", "KPRL-", "KPRL/", "KPRL 0057"]:
    check_raises("reject %r" % (bad,), lambda b=bad: KM.check_staff_id(b))
check("variants dash", KM.staff_id_variants("KPRL-043"), ["KPRL-043", "KPRL/043"])
check("variants slash", KM.staff_id_variants("KPRL/043"), ["KPRL/043", "KPRL-043"])
if FAILS:
    print("FAILURES: %s" % FAILS)
    raise SystemExit(1)
print("ALL STAFF-ID TESTS PASSED")
