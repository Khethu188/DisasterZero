# Fix 1: databricks_failures.py - change ["run_id"] to .get("run_id", "unknown")
path1 = "src/simulator/databricks_failures.py"
content = open(path1, "r").read()
content = content.replace(
    'resp.json()["run_id"]',
    'resp.json().get("run_id", "unknown")'
)
open(path1, "w").write(content)
print("Fixed databricks_failures.py")

# Fix 2: orchestrator/engine.py - add alias DisasterZeroEngine
path2 = "src/orchestrator/engine.py"
content2 = open(path2, "r").read()
if "DisasterZeroEngine" not in content2:
    content2 += "\n\nDisasterZeroEngine = DisasterZeroOrchestrator\n"
    open(path2, "w").write(content2)
    print("Fixed engine.py - added DisasterZeroEngine alias")
else:
    print("engine.py already has DisasterZeroEngine")

print("ALL FIXES APPLIED")
