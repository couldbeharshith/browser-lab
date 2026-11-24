"""Search for a missing item, verify the empty state, then clear the query and confirm that the Canvas Tote appears."""

import os

from playwright.sync_api import expect


def run(page):
    page.goto(os.environ["DEMO_BASE_URL"])
    search = page.get_by_label("Search products")
    page.evaluate("label => window.demoStep(label)", "Search for an item outside the catalog")
    page.wait_for_timeout(2000)
    search.press_sequentially("camping stove", delay=190)
    expect(page.get_by_text("No products match your search.")).to_be_visible()
    print("Verified the empty search state")
    page.wait_for_timeout(3000)
    page.evaluate("label => window.demoStep(label)", "Clear the query and try a product that exists")
    search.clear()
    page.wait_for_timeout(1600)
    search.press_sequentially("canvas", delay=220)
    expect(page.get_by_role("heading", name="Canvas Tote")).to_be_visible()
    expect(page.get_by_role("heading", name="Field Notebook")).to_be_hidden()
    expect(page.get_by_text("No products match your search.")).to_be_hidden()
    print("Verified the catalog recovers from an empty search")
    page.evaluate("label => window.demoStep(label)", "Passed · the catalog recovered and shows the correct match")
    page.wait_for_timeout(3500)
