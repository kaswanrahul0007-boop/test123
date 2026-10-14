"""Record your mouse/keyboard once, replay it later (works on any app, but fragile if windows move)."""
import json
import time
from pathlib import Path


def record(out: str):
    from pynput import mouse, keyboard
    events, t0 = [], time.time()
    stop = {"v": False}

    def add(kind, **kw):
        events.append({"t": round(time.time() - t0, 3), "kind": kind, **kw})

    def on_click(x, y, button, pressed):
        if pressed:
            add("click", x=x, y=y, button=button.name)

    def on_press(key):
        if key == keyboard.Key.esc:
            stop["v"] = True
            return False
        add("key", key=getattr(key, "char", None) or str(key))

    print("Recording... do your task, press ESC to stop.")
    with mouse.Listener(on_click=on_click) as ml, keyboard.Listener(on_press=on_press) as kl:
        kl.join()
        ml.stop()
    Path(out).write_text(json.dumps(events, indent=1), encoding="utf-8")
    print(f"Saved {len(events)} events to {out}")


def replay(src: str, speed: float = 1.0):
    import pyautogui
    pyautogui.FAILSAFE = True  # slam mouse into a screen corner to abort
    events = json.loads(Path(src).read_text(encoding="utf-8"))
    print("Replaying in 3s. Move mouse to a screen corner to abort.")
    time.sleep(3)
    last = 0
    for e in events:
        time.sleep(max(0, (e["t"] - last) / speed))
        last = e["t"]
        if e["kind"] == "click":
            pyautogui.click(e["x"], e["y"], button=e["button"])
        elif e["kind"] == "key":
            k = e["key"]
            if k.startswith("Key."):
                pyautogui.press(k[4:])
            else:
                pyautogui.write(k)
