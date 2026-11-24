"""Search for the Field Notebook and add it twice. Verify that the subtotal rises from $12.00 to $24.00."""

import os

from playwright.sync_api import expect


def run(page):
    page.goto(os.environ["DEMO_BASE_URL"])
    page.evaluate("label => window.demoStep(label)", "Find the Field Notebook in the catalog")
    page.wait_for_timeout(2400)
    page.get_by_label("Search products").press_sequentially("notebook", delay=220)
    page.wait_for_timeout(2300)
    page.evaluate("label => window.demoStep(label)", "Add one Field Notebook and check the subtotal")
    print("Adding a Field Notebook to the cart")
    page.get_by_role("button", name="Add Field Notebook").click()
    expect(page.get_by_test_id("cart-count")).to_have_text("1 item")
    expect(page.get_by_test_id("cart-total")).to_have_text("$12.00")
    print("Verified one item and a $12.00 total")
    page.wait_for_timeout(2900)
    page.evaluate("label => window.demoStep(label)", "Add a second notebook and verify the quantity and total")
    page.get_by_role("button", name="Add Field Notebook").click()
    expect(page.get_by_test_id("cart-count")).to_have_text("2 items")
    expect(page.get_by_test_id("cart-total")).to_have_text("$24.00")
    print("Verified two items and a $24.00 total")
    page.wait_for_timeout(3700)
