import argparse
import logging
import time
from botlib import config, tasks


def cmd_schedule(cfg):
    import schedule
    for j in cfg.get("schedule", []):
        every = schedule.every()
        unit = getattr(every, j["every"])  # day, monday, hour...
        unit.at(j["at"]).do(lambda n=j["task"]: print(tasks.run(n, cfg)))
        print(f"scheduled {j['task']} {j['every']} @ {j['at']}")
    print("Bot running. Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(30)


def main():
    ap = argparse.ArgumentParser(prog="laptopbot")
    ap.add_argument("--config")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    r = sub.add_parser("run"); r.add_argument("task")
    sub.add_parser("schedule")
    a = sub.add_parser("agent"); a.add_argument("goal")
    rec = sub.add_parser("record"); rec.add_argument("out")
    rep = sub.add_parser("replay"); rep.add_argument("src"); rep.add_argument("--speed", type=float, default=1.0)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO)
    if args.cmd in ("record", "replay"):
        from botlib import recorder
        return recorder.record(args.out) if args.cmd == "record" else recorder.replay(args.src, args.speed)
    cfg = config.load(args.config)
    if args.cmd == "list":
        print("\n".join(sorted(tasks.load_all())))
    elif args.cmd == "run":
        print(tasks.run(args.task, cfg))
    elif args.cmd == "schedule":
        cmd_schedule(cfg)
    elif args.cmd == "agent":
        from botlib.agent import run_agent
        run_agent(args.goal, cfg)


if __name__ == "__main__":
    main()
