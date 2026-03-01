import sys, json

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        r = json.loads(line)
    except json.JSONDecodeError:
        continue
    task = r.get("task", "").replace("\n", " ").strip()[:45]
    conf = r.get("mongo_confidence", "?")
    conf_str = f"{conf:.3f}" if isinstance(conf, float) else str(conf)
    print(
        f"run={str(r.get('run_idx','?')):>2} "
        f"steps={str(r.get('steps','?')):>2} "
        f"judge={str(r.get('judge_validated','?')):>5} "
        f"conf={conf_str:>5} "
        f"path_ok={str(r.get('path_update_allowed','?')):>5} "
        f"task={task}"
    )
