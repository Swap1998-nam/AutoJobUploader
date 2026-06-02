"""Run: python view_db.py"""
import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "applications.db"

with sqlite3.connect(DB) as conn:
    conn.row_factory = sqlite3.Row

    print("\n===== SUMMARY =====")
    total   = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    applied = conn.execute("SELECT COUNT(*) FROM applications WHERE status IN ('applied','manually-applied')").fetchone()[0]
    auto    = conn.execute("SELECT COUNT(*) FROM applications WHERE method='auto'").fetchone()[0]
    manual  = conn.execute("SELECT COUNT(*) FROM applications WHERE method='manual'").fetchone()[0]
    failed  = conn.execute("SELECT COUNT(*) FROM applications WHERE status='failed'").fetchone()[0]
    print(f"  Total logged : {total}")
    print(f"  Applied      : {applied}  (auto: {auto}, manual: {manual})")
    print(f"  Failed       : {failed}")

    print("\n===== ALL APPLICATIONS =====")
    rows = conn.execute(
        "SELECT title, company, platform, status, method, applied_at FROM applications ORDER BY applied_at DESC"
    ).fetchall()

    if not rows:
        print("  No applications recorded yet.")
    else:
        fmt = "{:<35} {:<25} {:<10} {:<18} {:<7} {}"
        print(fmt.format("Title", "Company", "Platform", "Status", "Method", "Applied At"))
        print("-" * 115)
        for r in rows:
            print(fmt.format(
                (r["title"] or "")[:34],
                (r["company"] or "")[:24],
                r["platform"],
                r["status"],
                r["method"],
                r["applied_at"][:19]
            ))
