"""
pay_bill.py
CLI entry point: scan a bill and pay it through your Citibank checking account.

Usage:
    python pay_bill.py auth
    python pay_bill.py scan invoice.pdf
    python pay_bill.py pay  invoice.pdf --token <access_token>
    python pay_bill.py pay  invoice.jpg --token <access_token> --date 2024-04-01
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path

import click
from dotenv import load_dotenv

load_dotenv()  # Load .env if present

from bill_scanner import scan_bill
from bill_parser import parse_bill, BillInfo
from citibank_client import (
    CitiConfig,
    CitibankAuthError,
    CitibankPaymentError,
    get_authorization_url,
    exchange_code_for_token,
    get_account_balance,
    schedule_payment,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_config() -> CitiConfig:
    try:
        return CitiConfig.from_env()
    except EnvironmentError as exc:
        click.echo(f"Configuration error: {exc}", err=True)
        sys.exit(1)


def _parse_date(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise click.BadParameter(
        f"'{value}' is not a recognised date. Use YYYY-MM-DD, MM/DD/YYYY, or MM/DD/YY."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """Scan bills and pay them automatically via your Citibank checking account."""


@cli.command("auth")
def auth_cmd():
    """
    Step 1 – Authorize the application with Citibank.

    Opens the OAuth URL and exchanges the returned code for tokens.
    """
    config = _load_config()

    auth_url = get_authorization_url(config)
    click.echo("\nOpen this URL in your browser to authorize access to your Citibank account:\n")
    click.echo(f"  {auth_url}\n")
    click.echo("After authorizing, Citibank will redirect you to your redirect_uri with a 'code' parameter.")

    auth_code = click.prompt("\nPaste the authorization code here")
    try:
        token_data = exchange_code_for_token(config, auth_code.strip())
    except CitibankAuthError as exc:
        click.echo(f"Authorization failed: {exc}", err=True)
        sys.exit(1)

    click.echo("\nAuthorization successful. Save your tokens securely:\n")
    click.echo(f"  access_token  : {token_data.get('access_token')}")
    click.echo(f"  refresh_token : {token_data.get('refresh_token')}")
    expires = token_data.get("expires_in")
    if expires:
        click.echo(f"  expires_in    : {expires} seconds")
    click.echo(
        "\nPass --token <access_token> to the 'pay' command, "
        "or store it as CITI_ACCESS_TOKEN in your .env file."
    )


@cli.command("scan")
@click.argument("bill_file")
def scan_cmd(bill_file: str):
    """
    Scan a bill file and display the extracted payment details.

    BILL_FILE can be a PDF, JPG, PNG, or TIFF.
    """
    click.echo(f"Scanning {bill_file} ...")
    try:
        raw_text = scan_bill(bill_file)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        click.echo(f"Scan error: {exc}", err=True)
        sys.exit(1)

    bill = parse_bill(raw_text)

    click.echo("\n--- Extracted Bill Information ---")
    click.echo(str(bill))

    if not bill.is_complete():
        click.echo(
            "\nWarning: could not extract all required fields. "
            "You may need to provide --amount and/or --payee overrides when running 'pay'.",
            err=True,
        )


@cli.command("pay")
@click.argument("bill_file")
@click.option(
    "--token",
    envvar="CITI_ACCESS_TOKEN",
    required=True,
    help="OAuth 2.0 access token (or set CITI_ACCESS_TOKEN in .env).",
)
@click.option(
    "--date", "payment_date_str",
    default=None,
    help="Payment date in YYYY-MM-DD format. Defaults to bill due date, then today.",
)
@click.option("--payee", default=None, help="Override payee name extracted from bill.")
@click.option("--amount", default=None, type=float, help="Override amount extracted from bill.")
@click.option("--dry-run", is_flag=True, help="Parse and validate without submitting payment.")
def pay_cmd(
    bill_file: str,
    token: str,
    payment_date_str: str,
    payee: str,
    amount: float,
    dry_run: bool,
):
    """
    Scan a bill file and pay it from your Citibank checking account.

    BILL_FILE can be a PDF, JPG, PNG, or TIFF.
    """
    config = _load_config()

    # --- Scan & parse ---
    click.echo(f"Scanning {bill_file} ...")
    try:
        raw_text = scan_bill(bill_file)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        click.echo(f"Scan error: {exc}", err=True)
        sys.exit(1)

    bill = parse_bill(raw_text)

    # Apply CLI overrides
    if payee:
        bill.payee = payee
    if amount is not None:
        bill.amount_due = amount

    click.echo("\n--- Extracted Bill Information ---")
    click.echo(str(bill))

    if not bill.is_complete():
        click.echo(
            "\nError: could not determine payee and/or amount. "
            "Use --payee and/or --amount to supply them manually.",
            err=True,
        )
        sys.exit(1)

    # Determine payment date
    if payment_date_str:
        try:
            pay_date = _parse_date(payment_date_str)
        except click.BadParameter as exc:
            click.echo(str(exc), err=True)
            sys.exit(1)
    elif bill.due_date:
        pay_date = bill.due_date
        click.echo(f"\nUsing bill due date as payment date: {pay_date}")
    else:
        pay_date = date.today()
        click.echo(f"\nNo due date found; scheduling for today: {pay_date}")

    # --- Confirm with user ---
    click.echo(
        f"\nReady to pay ${bill.amount_due:.2f} to '{bill.payee}' "
        f"on {pay_date} from Citibank account ending in "
        f"...{config.account_id[-4:]}."
    )

    if dry_run:
        click.echo("\n[Dry run] Payment not submitted.")
        return

    if not click.confirm("Proceed with payment?"):
        click.echo("Payment cancelled.")
        return

    # --- Check balance ---
    try:
        balance_data = get_account_balance(config, token)
        available = balance_data.get("availableBalance", {}).get("amount")
        if available is not None and float(available) < bill.amount_due:
            click.echo(
                f"Insufficient funds: available ${available:.2f}, "
                f"payment ${bill.amount_due:.2f}.",
                err=True,
            )
            sys.exit(1)
    except CitibankPaymentError as exc:
        click.echo(f"Could not verify balance: {exc}", err=True)
        # Continue anyway; the payment API will reject it if insufficient

    # --- Submit payment ---
    memo = bill.invoice_number or bill.account_number or ""
    try:
        result = schedule_payment(
            config,
            token,
            payee_name=bill.payee,
            amount=bill.amount_due,
            payment_date=pay_date,
            memo=memo or None,
        )
    except CitibankPaymentError as exc:
        click.echo(f"Payment failed: {exc}", err=True)
        sys.exit(1)

    confirmation = result.get("confirmationNumber") or result.get("paymentId") or "N/A"
    click.echo(f"\nPayment scheduled successfully. Confirmation number: {confirmation}")


if __name__ == "__main__":
    cli()
