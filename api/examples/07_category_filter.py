"""Browse the Desk collection, search for a tote, then switch to Carry and verify that the matching product appears."""

import os

from playwright.sync_api import expect


def run(page):
    page.goto(os.environ["DEMO_BASE_URL"])
    page.evaluate("label => window.demoStep(label)", "Open the Desk collection")
    page.wait_for_timeout(2300)
    page.get_by_role("button", name="Desk", exact=True).click()
    expect(page.get_by_role("heading", name="Field Notebook")).to_be_visible()
    expect(page.get_by_role("heading", name="Canvas Tote")).to_be_hidden()
    print("Desk shows the notebook and hides the tote")
    page.wait_for_timeout(2700)
    page.evaluate("label => window.demoStep(label)", "Search for a tote while Desk is selected")
    page.get_by_label("Search products").press_sequentially("tote", delay=260)
    expect(page.get_by_text("No products match your search.")).to_be_visible()
    page.wait_for_timeout(3400)
    page.evaluate("label => window.demoStep(label)", "Switch to Carry without clearing the search")
    page.get_by_role("button", name="Carry", exact=True).click()
    expect(page.get_by_role("heading", name="Canvas Tote")).to_be_visible()
    expect(page.get_by_label("Search products")).to_have_value("tote")
    print("Carry returns the tote while preserving the search query")
    page.wait_for_timeout(3700)
