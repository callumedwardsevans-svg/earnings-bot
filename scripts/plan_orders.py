"""Plan only (no reconcile, no report): see scripts/evening.py, which runs the full evening sequence."""
import sys

from evening import main  # noqa: E402

if __name__ == "__main__":
    print("plan_orders.py runs the full evening sequence (reconcile -> plan -> report); see scripts/evening.py")
    sys.exit(main())
