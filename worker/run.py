import argparse
import json
import os
import runpy
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from playwright.sync_api import Error, sync_playwright


EXPECTED_HEADINGS = {
    "pass": "Browser check demo",
    "fail": "Welcome to the demo",
}


def run_check(run_id, check):
    folder = Path(os.environ.get("ARTIFACT_DIR", "/artifacts")) / run_id
    folder.mkdir(parents=True, exist_ok=True)
    screenshot = folder / "screenshot.png"
    pending_screenshot = folder / "screenshot.tmp"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 960, "height": 540})
            page.set_default_timeout(15_000)
            page.goto(Path(__file__).with_name("demo.html").resolve().as_uri())
            heading = page.get_by_role("heading", level=1)
            heading.wait_for()
            actual = heading.inner_text().strip()
            page.screenshot(path=pending_screenshot, type="png")
            pending_screenshot.replace(screenshot)
            browser.close()

        expected = EXPECTED_HEADINGS[check]
        passed = actual == expected
        message = f'Found the expected heading “{actual}”.' if passed else f'Expected “{expected}”, found “{actual}”.'
    except Error as error:
        passed = False
        message = f"Browser check stopped: {str(error).splitlines()[0]}"

    pending_result = folder / "result.tmp"
    pending_result.write_text(json.dumps({"message": message}), encoding="utf-8")
    pending_result.replace(folder / "result.json")
    print(message)
    return 0 if passed else 1


def run_uploaded_check(run_id, record_video):
    folder = Path(os.environ.get("ARTIFACT_DIR", "/artifacts")) / run_id
    passed = False
    message = "The browser did not start."
    with (folder / "run.log").open("w", encoding="utf-8", buffering=1) as log:
        with redirect_stdout(log), redirect_stderr(log):
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    options = {"viewport": {"width": 960, "height": 540}}
                    if record_video:
                        options.update(record_video_dir=folder, record_video_size={"width": 960, "height": 540})
                    context = browser.new_context(**options)
                    page = context.new_page()
                    page.set_default_timeout(10_000)
                    recording = page.video
                    try:
                        print("Chromium started")
                        check = runpy.run_path(str(folder / "script.py")).get("run")
                        if not callable(check):
                            raise ValueError("Define a synchronous run(page) function in the script.")
                        check(page)
                        passed, message = True, "Check completed successfully."
                    except (Exception, SystemExit) as error:
                        message = error_summary(error)
                        traceback.print_exc()
                    finally:
                        try:
                            pending = folder / "screenshot.tmp"
                            page.screenshot(path=pending, type="png", timeout=3_000)
                            pending.replace(folder / "screenshot.png")
                        except Error as error:
                            print(f"Screenshot unavailable: {error_summary(error)}")
                        context.close()
                        if recording:
                            Path(recording.path()).replace(folder / "video.webm")
                        browser.close()
            except (Exception, SystemExit) as error:
                if passed:
                    print(f"Artifact finalization failed: {error_summary(error)}")
                elif message == "The browser did not start.":
                    message = error_summary(error)
                traceback.print_exc()
            print(message)

    pending = folder / "result.tmp"
    pending.write_text(json.dumps({"message": message}), encoding="utf-8")
    pending.replace(folder / "result.json")
    print(message)
    return 0 if passed else 1


def error_summary(error):
    lines = str(error).strip().splitlines()
    return f"{type(error).__name__}: {lines[0]}" if lines else type(error).__name__


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a bundled browser check.")
    parser.add_argument("run_id")
    parser.add_argument("check", choices=[*EXPECTED_HEADINGS, "script"])
    parser.add_argument("--video", action="store_true")
    args = parser.parse_args()
    if args.check == "script":
        raise SystemExit(run_uploaded_check(args.run_id, args.video))
    raise SystemExit(run_check(args.run_id, args.check))
