from pathlib import Path
import runpy

path = Path(".github/scripts/apply_v330_review_fix.py")
source = path.read_text(encoding="utf-8")
old = '                store.move("prepared")\n'
new = '''                store.move(
                    "prepared",
                    attempt_id="attempt_12345678",
                    changes={
                        "attempt_id": "attempt_12345678",
                        "worktree_id": "worktree_12345678",
                        "worktree_path": "/tmp/worktree",
                        "branch_id": "branch_12345678",
                        "branch_name": "pathfinder/auto/test",
                    },
                )
'''
if source.count(old) != 1:
    raise SystemExit("prepared-state regression fixture did not match exactly once")
path.write_text(source.replace(old, new, 1), encoding="utf-8")
runpy.run_path(str(path), run_name="__main__")
