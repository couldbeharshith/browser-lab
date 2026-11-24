"""Try signing in with the wrong password, verify the error, then correct it and confirm the demo account signs in."""

import os

from playwright.sync_api import expect


def run(page):
    page.goto(os.environ["DEMO_BASE_URL"])
    page.evaluate("label => window.demoStep(label)", "Enter a deliberately incorrect password")
    page.wait_for_timeout(2100)
    page.get_by_role("button", name="Account").click()
    page.get_by_label("Email").press_sequentially("judge@example.com", delay=105)
    password = page.get_by_label("Password")
    password.press_sequentially("incorrect", delay=145)
    page.wait_for_timeout(1600)
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_text("That email or password is incorrect.")).to_be_visible()
    print("Sign-in error appears for an incorrect password")
    page.wait_for_timeout(2900)
    page.evaluate("label => window.demoStep(label)", "Correct the password and sign in again")
    password.clear()
    password.press_sequentially("demo-shop", delay=140)
    page.wait_for_timeout(1300)
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_role("status")).to_have_text("Signed in as judge@example.com")
    print("Corrected password signs into the demo account")
    page.wait_for_timeout(3700)
