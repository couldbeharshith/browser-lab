"""Sign in with the demo account, search for a notebook, and verify that the tote disappears from the results."""

import os

from playwright.sync_api import expect


def run(page):
    page.goto(os.environ["DEMO_BASE_URL"])
    page.evaluate("label => window.demoStep(label)", "Sign in with a demo account")
    print("Signing in with the demo account")
    page.wait_for_timeout(2200)
    page.get_by_role("button", name="Account").click()
    page.wait_for_timeout(850)
    page.get_by_label("Email").press_sequentially("judge@example.com", delay=115)
    page.wait_for_timeout(1100)
    page.get_by_label("Password").press_sequentially("demo-shop", delay=140)
    page.wait_for_timeout(1200)
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_role("status")).to_have_text("Signed in as judge@example.com")
    page.wait_for_timeout(2400)
    page.evaluate("label => window.demoStep(label)", "Search for a notebook and compare the results")
    print("Searching the catalog for a notebook")
    page.get_by_label("Search products").press_sequentially("notebook", delay=210)
    expect(page.get_by_role("heading", name="Field Notebook")).to_be_visible()
    expect(page.get_by_role("heading", name="Canvas Tote")).to_be_hidden()
    print("Verified the search results")
    page.evaluate("label => window.demoStep(label)", "Passed · the notebook is visible and the tote is filtered out")
    page.wait_for_timeout(3000)
