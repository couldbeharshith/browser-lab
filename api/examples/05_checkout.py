"""Add a notebook and tote, verify the $30.00 subtotal, then place a demo order and confirm the bag is empty."""

import os

from playwright.sync_api import expect


def run(page):
    page.goto(os.environ["DEMO_BASE_URL"])
    page.evaluate("label => window.demoStep(label)", "Start an order with two different products")
    page.wait_for_timeout(2400)
    page.get_by_role("button", name="Add Field Notebook").click()
    page.wait_for_timeout(2100)
    page.get_by_role("button", name="Add Canvas Tote").click()
    expect(page.get_by_test_id("cart-total")).to_have_text("$30.00")
    print("Verified the $30.00 subtotal")
    page.wait_for_timeout(2700)
    page.evaluate("label => window.demoStep(label)", "Open checkout and enter a delivery name")
    page.get_by_role("button", name="Checkout").click()
    page.wait_for_timeout(1200)
    page.get_by_label("Delivery name").press_sequentially("Alex Rivera", delay=150)
    page.wait_for_timeout(1500)
    page.evaluate("label => window.demoStep(label)", "Place the demo order and check the confirmation")
    page.get_by_role("button", name="Place demo order").click()
    expect(page.get_by_text("Order confirmed for Alex Rivera.")).to_be_visible()
    expect(page.get_by_test_id("cart-count")).to_have_text("0 items")
    print("Verified order confirmation and cleared cart")
    page.wait_for_timeout(3600)
