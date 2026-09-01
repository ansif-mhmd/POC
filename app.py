"""
FMCSA Out-of-Service Sales Opportunity Agent - Local MVP Application
=====================================================================
Run this application locally to interact with the Sales Opportunity Agent.

Usage:
  python app.py --demo         Run automated demonstration suite (Mode 1 & Mode 2)
  python app.py                Interactive natural language session
"""

import sys
import os
import argparse

# Force stdout UTF-8 encoding for Windows terminals
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from sales_opportunity_agent import SalesOpportunityAgent


def print_banner():
    print("=" * 75)
    print(" [FMCSA OOS] Sales Opportunity AI Agent - Local MVP")
    print("=" * 75)


def run_demo(agent: SalesOpportunityAgent):
    print("\n---------------------------------------------------------------------------")
    print(" > RUNNING DEMO SCENARIO 1: Mode 1 - Summary of Last 5 OOS Notifications")
    print("---------------------------------------------------------------------------")
    query_1 = "Find the last 5 carriers placed out of service daily"
    print(f"User Query: '{query_1}'\n")
    res_1 = agent.process_request(query_1, limit=5)
    print(res_1["formatted_output"])

    print("\n---------------------------------------------------------------------------")
    print(" > RUNNING DEMO SCENARIO 2: Mode 2 - Lead Outreach Script Generation")
    print("---------------------------------------------------------------------------")
    query_2 = "Generate a lead outreach script for the most recent out of service carrier"
    print(f"User Query: '{query_2}'\n")
    res_2 = agent.process_request(query_2, limit=1)
    print(res_2["formatted_output"])
    print("\n---------------------------------------------------------------------------")
    print(" SUCCESS: DEMO EXECUTION COMPLETE!")
    print("---------------------------------------------------------------------------\n")


def run_interactive(agent: SalesOpportunityAgent):
    print_banner()
    print("Type your request below (or 'exit' to quit).")
    print("Examples:")
    print("  1. 'Summarize the last 5 out of service notifications'")
    print("  2. 'Generate an outreach script for the top lead'")
    print("---------------------------------------------------------------------------\n")

    while True:
        try:
            user_input = input("Sales Rep > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Exiting Sales Opportunity Agent. Goodbye!")
                break

            response = agent.process_request(user_input, limit=5)
            print("\n" + response["formatted_output"] + "\n")
            print("-" * 75)

        except (KeyboardInterrupt, EOFError):
            print("\nExiting Sales Opportunity Agent.")
            break


def main():
    parser = argparse.ArgumentParser(description="FMCSA Sales Opportunity Agent MVP")
    parser.add_argument("--demo", action="store_true", help="Run non-interactive demo suite")
    parser.add_argument("--live", action="store_true", help="Use live API calls to transportation.gov")
    args = parser.parse_args()

    agent = SalesOpportunityAgent(use_live_api=args.live)

    if args.demo:
        print_banner()
        run_demo(agent)
    else:
        run_interactive(agent)


if __name__ == "__main__":
    main()
