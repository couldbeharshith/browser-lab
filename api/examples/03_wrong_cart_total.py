"""Search for the Canvas Tote and add it to the bag. Expect $1.00 instead of $18.00 to demonstrate an assertion failure."""

import os


def run(page):
    page.goto(os.environ["DEMO_BASE_URL"])
    page.evaluate("label => window.demoStep(label)", "Search for the Canvas Tote")
    page.wait_for_timeout(2300)
    page.get_by_label("Search products").press_sequentially("canvas tote", delay=200)
    page.wait_for_timeout(2400)
    page.evaluate("label => window.demoStep(label)", "Add the tote to the cart")
    print("Adding a Canvas Tote to the cart")
    page.get_by_role("button", name="Add Canvas Tote").click()
    page.wait_for_timeout(2600)
    total = page.get_by_test_id("cart-total").inner_text()
    page.evaluate("label => window.demoStep(label)", f"Intentional mismatch · expecting $1.00, actual total {total}")
    page.wait_for_timeout(4400)
    assert total == "$1.00", f"Expected a $1.00 cart total, but the shop shows {total}."
