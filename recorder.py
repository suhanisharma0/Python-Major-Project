import argparse
import signal
import sys
import time
from datetime import datetime

import cv2
import mss
import numpy as np


def parse_args():
    p = argparse.ArgumentParser(description="Python screen recorder")
    p.add_argument("-o", "--output", default=None,
                   help="Output file (default: recording_YYYYmmdd_HHMMSS.mp4)")
    p.add_argument("--fps", type=int, default=20, help="Frames per second (default 20)")
    p.add_argument("-d", "--duration", type=float, default=0,
                   help="Seconds to record; 0 = until Ctrl+C")
    p.add_argument("--monitor", type=int, default=1,
                   help="Monitor index (0 = all screens, 1 = primary)")
    p.add_argument("--region", type=int, nargs=4,
                   metavar=("LEFT", "TOP", "WIDTH", "HEIGHT"),
                   help="Record only this region")
    p.add_argument("--scale", type=float, default=1.0,
                   help="Resize factor, e.g. 0.5 for half size")
    p.add_argument("--countdown", type=int, default=0,
                   help="Seconds to wait before starting")
    p.add_argument("--preview", action="store_true",
                   help="Show live preview window (press q to stop)")
    p.add_argument("--codec", default="mp4v",
                   help="FourCC codec (mp4v for .mp4, XVID for .avi)")
    return p.parse_args()


def main():
    args = parse_args()
    out = args.output or f"recording_{datetime.now():%Y%m%d_%H%M%S}.mp4"

    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(flag=True))

    with mss.mss() as sct:
        if args.region:
            l, t, w, h = args.region
            area = {"left": l, "top": t, "width": w, "height": h}
        else:
            if args.monitor >= len(sct.monitors):
                sys.exit(f"Monitor {args.monitor} not found "
                         f"(available: 0-{len(sct.monitors) - 1})")
            area = sct.monitors[args.monitor]

        width = int(area["width"] * args.scale)
        height = int(area["height"] * args.scale)
        # Some codecs need even dimensions
        width -= width % 2
        height -= height % 2

        writer = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*args.codec),
                                 args.fps, (width, height))
        if not writer.isOpened():
            sys.exit("Could not open video writer. Try --codec XVID with a .avi output.")

        for i in range(args.countdown, 0, -1):
            print(f"Starting in {i}...")
            time.sleep(1)

        print(f"Recording {width}x{height} @ {args.fps} fps -> {out}")
        print("Press Ctrl+C" + (" or 'q' in preview" if args.preview else "") + " to stop.")

        frame_time = 1.0 / args.fps
        start = time.perf_counter()
        next_frame = start
        frames = 0

        while not stop["flag"]:
            now = time.perf_counter()
            if args.duration and now - start >= args.duration:
                break

            img = np.array(sct.grab(area))               # BGRA
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            if args.scale != 1.0 or frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

            writer.write(frame)
            frames += 1

            if args.preview:
                cv2.imshow("Preview (q to stop)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            # Keep a steady frame rate; skip sleeping if we're running behind
            next_frame += frame_time
            delay = next_frame - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                next_frame = time.perf_counter()

        writer.release()
        if args.preview:
            cv2.destroyAllWindows()

    elapsed = time.perf_counter() - start
    print(f"Saved {out}: {frames} frames in {elapsed:.1f}s "
          f"(~{frames / max(elapsed, 1e-6):.1f} fps captured)")


if __name__ == "__main__":
    main()
