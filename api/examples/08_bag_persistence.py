"""Add a tote and a notebook, reload the storefront, then verify both items and their $30.00 subtotal are still in the bag."""

import os

from playwright.sync_api import expect


def run(page):
    page.goto(os.environ["DEMO_BASE_URL"])
    page.evaluate("label => window.demoStep(label)", "Add a tote and a notebook to the bag")
    page.wait_for_timeout(2200)
    page.get_by_role("button", name="Add Canvas Tote").click()
    page.wait_for_timeout(1900)
    page.get_by_role("button", name="Add Field Notebook").click()
    expect(page.get_by_test_id("cart-total")).to_have_text("$30.00")
    print("Bag contains two different products before reload")
    page.wait_for_timeout(2800)
    page.evaluate("label => window.demoStep(label)", "Reload the storefront with the bag populated")
    page.wait_for_timeout(2300)
    page.reload()
    page.evaluate("label => window.demoStep(label)", "Passed · both products and the $30.00 subtotal survived the reload")
    expect(page.locator("#bag-items")).to_contain_text("Canvas Tote")
    expect(page.locator("#bag-items")).to_contain_text("Field Notebook")
    expect(page.get_by_test_id("cart-count")).to_have_text("2 items")
    expect(page.get_by_test_id("cart-total")).to_have_text("$30.00")
    print("Bag contents and subtotal persisted across reload")
    page.wait_for_timeout(4600)
