"""Add two products and remove them one at a time. Verify the updated subtotal and that an empty bag disables checkout."""

import os

from playwright.sync_api import expect


def run(page):
    page.goto(os.environ["DEMO_BASE_URL"])
    page.evaluate("label => window.demoStep(label)", "Add a notebook and a tote to the cart")
    page.wait_for_timeout(2300)
    page.get_by_role("button", name="Add Field Notebook").click()
    page.wait_for_timeout(1900)
    page.get_by_role("button", name="Add Canvas Tote").click()
    expect(page.get_by_test_id("cart-total")).to_have_text("$30.00")
    page.wait_for_timeout(2600)
    page.evaluate("label => window.demoStep(label)", "Remove the last item and verify the new total")
    page.get_by_role("button", name="Remove last item").click()
    expect(page.get_by_test_id("cart-count")).to_have_text("1 item")
    expect(page.get_by_test_id("cart-total")).to_have_text("$12.00")
    print("Verified the removed item no longer contributes to the total")
    page.wait_for_timeout(2700)
    page.evaluate("label => window.demoStep(label)", "Empty the cart and confirm checkout is disabled")
    page.get_by_role("button", name="Remove last item").click()
    expect(page.get_by_test_id("cart-total")).to_have_text("$0.00")
    expect(page.get_by_role("button", name="Checkout")).to_be_disabled()
    print("Verified an empty cart disables checkout")
    page.wait_for_timeout(3600)
