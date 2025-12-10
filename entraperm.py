import argparse
import requests
import json
import csv
import os
import sys

GRAPH = "https://graph.microsoft.com/beta"

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

def color(t, c): return f"{c}{t}{RESET}"

def resource_path(filename):
    # Works when executed normally OR installed via pip/pipx
    base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path+"/data/", filename)

def load_token():
    auth_file = ".roadtools_auth"
    if not os.path.exists(auth_file):
        print(color(f"ERROR: {auth_file} not found.", RED))
        sys.exit(1)
    with open(auth_file, "r") as f:
        d = json.load(f)
    tok = d.get("accessToken")
    if not tok:
        print(color("ERROR: accessToken missing.", RED))
        sys.exit(1)
    return tok

def graph_get(url, token):
    r = requests.get(url, headers={"Authorization": f"Bearer {token}", "ConsistencyLevel": "eventual"})
    r.raise_for_status()
    return r.json()

def graph_post(url, payload, token):
    r = requests.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=payload)
    r.raise_for_status()
    return r.json()

def fetch_all_namespaces(token):
    out = []
    url = f"{GRAPH}/roleManagement/directory/resourceNamespaces"
    while url:
        d = graph_get(url, token)
        out += [x["name"] for x in d.get("value", [])]
        url = d.get("@odata.nextLink")
    return out

def fetch_all_actions(token, ns):
    out = []
    url = f"{GRAPH}/roleManagement/directory/resourceNamespaces/{ns}/resourceActions?$select=name&$top=999"
    while url:
        d = graph_get(url, token)
        out += [x["name"] for x in d.get("value", [])]
        url = d.get("@odata.nextLink")
    return out

def resolve_scopes(token, scope_input):
    scope_input = scope_input.lower().strip()
    special = ["users", "devices"]
    scopes = []

    if scope_input in special:
        print(color(f"Fetching all {scope_input}...", BLUE))
        url = f"{GRAPH}/{scope_input}?$select=id&$top=999"
        while url:
            d = graph_get(url, token)
            scopes += ["/" + obj["id"] for obj in d.get("value", [])]
            url = d.get("@odata.nextLink")
    else:
        scopes = [s if s.startswith("/") else f"/{s}" for s in scope_input.split(",")]

    return scopes

# -----------------------------------------------------------
# COLLECT
# -----------------------------------------------------------
def do_collect(args, token):
    print(color("Collecting namespaces...\n", BLUE))
    namespaces = fetch_all_namespaces(token)
    collected = {}

    for ns in namespaces:
        print(color(f"Collecting actions for {ns}", BLUE))
        collected[ns] = fetch_all_actions(token, ns)

    with open("collected_actions.json", "w") as f:
        json.dump(collected, f, indent=2)

    print(color("\nSaved to collected_actions.json", BLUE))

# -----------------------------------------------------------
# CHECK
# -----------------------------------------------------------
def do_check(args, token):
    if not os.path.exists(args.collected):
        print(color(f"ERROR: {args.collected} missing.", RED))
        sys.exit(1)

    with open(args.collected, "r") as f:
        collected = json.load(f)
    
    # Load default results if available
    default_map = {}
    if os.path.exists(resource_path("default_results.csv")):
        with open(resource_path("default_results.csv"), "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["namespace"], row["action"], row["scope"])
                default_map[key] = row["decision"]

    scopes = resolve_scopes(token, args.scope)
    results = []

    MAX_CHUNK = 20

    def chunk_list(lst, size):
        for i in range(0, len(lst), size):
            yield lst[i:i+size]

    for ns, actions in collected.items():

        # If user provided --action, override list
        if args.action:
            actions = [args.action]
            args.namespace = args.action.split("/")[0]  # ensure namespace filter matches

        # Namespace filtering
        if args.namespace and ns != args.namespace:
            continue

        # Filter only actions where default result is not invalidAction if requested
        if args.valid:
            filtered_actions = [act for act in actions if default_map.get((ns, act, "/")) != "invalidAction"]
            actions = filtered_actions
        
        if actions == []:
            continue
        
        print(color(f"\nChecking {ns}...", BLUE))

        # Build full list of checks first
        all_checks = [
            {"resourceAction": act, "directoryScopeId": scope}
            for act in actions
            for scope in scopes
        ]


        # Process in chunks
        for chunk in chunk_list(all_checks, MAX_CHUNK):

            payload = {
                "resourceActionAuthorizationChecks": chunk
            }

            try:
                resp = graph_post(
                    f"{GRAPH}/roleManagement/directory/estimateAccess",
                    payload,
                    token
                )
            except Exception as e:
                print(color(f"Error during chunk request: {e}", RED))
                continue

            # Parse result from this chunk
            for item in resp.get("value", []):
                ns_name = ns
                action = item["resourceAction"]
                decision = item["accessDecision"]
                scope = item["directoryScopeId"]
                default_decision = default_map.get((ns_name, action, scope), "")

                expected = (decision == default_decision)

                # Color decision
                if decision == "allowed":
                    sym = color("🟢 allowed", GREEN)
                elif decision == "conditional":
                    sym = color("🟡 conditional", YELLOW)
                elif decision == "notAllowed":
                    sym = color("🔴 notAllowed", RED)
                else:
                    sym = color(f"❌ {decision}", RED)

                print(f"{action:70} => {sym} {scope}")
                results.append((ns_name, action, scope, decision, default_decision, expected))

    # Save results
    with open("action_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["namespace", "action", "scope", "decision", "default_decision", "expected"])
        writer.writerows(results)

    print(color("\nSaved to action_results.csv", BLUE))
# -------------------------------------------------------------
# MAIN
# -------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Graph permission collector/checker"
    )

    subparsers = parser.add_subparsers(dest="mode", required=True)

    # --- collect ---
    p_collect = subparsers.add_parser("collect", help="Collect all namespaces/actions")
    p_collect.set_defaults(func=do_collect)

    # --- check ---
    p_check = subparsers.add_parser("check", help="Check collected permissions")
    p_check.add_argument("--collected", default=resource_path("collected_actions.json"), help="Path to collected JSON")
    p_check.add_argument("--namespace", help="Filter namespace")
    p_check.add_argument("--action", help="Filter a specific action (will ignore --namespace if specified)")
    p_check.add_argument("--scope", default="/", help='scope to use, default is "/" can be for example users, devices, /oid1, "/oid1,/oid2"')
    p_check.add_argument("--valid", action="store_true", help="Only test actions where default result is not invalidAction")
    p_check.set_defaults(func=do_check)

    args = parser.parse_args()

    print(color("Loading token...\n", BLUE))
    token = load_token()

    args.func(args, token)

if __name__ == "__main__":
    main()