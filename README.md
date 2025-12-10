# EntraPerm

**Entra ID Permissions Checker**

`entraperm` is a lightweight Python tool to collect and check Microsoft Entra ID (Azure AD) resource action permissions for users, devices, and other directory scopes. It helps identify unexpected access or misconfigurations in your tenant.

---

## Features

- Collect all namespaces and actions from Microsoft Graph.
- Check a user's permissions against the collected actions.
- Compare results with a default user to spot unexpected access.
- Supports filtering by namespace, action, or scope (users/devices/OIDs).
- Outputs results in CSV for easy analysis.

---

## Installation

```bash
pipx install git+https://github.com/Mauriceter/EntraPerm
```

## Usage

Authentication the the Graph API is donne using a .roadtools_auth file in the current directory. Such file can be obtain using [ROADTools](https://github.com/dirkjanm/ROADtools).

```
roadtx auth -t ... -u ... -p ...
```

### Collect

This mode can be use to collect all namespaces and actions and store them in a CSV, this mode is not usefull in moset cases.

```
entraperm collect -h
usage: entraperm collect [-h]

options:
  -h, --help  show this help message and exit
```

### Check

This mode use the list of namespaces and actions to test permissions using the `/roleManagement/directory/estimateAccess` endpoint.

```
entraperm check -h  
usage: entraperm check [-h] [--collected COLLECTED] [--namespace NAMESPACE] [--action ACTION] [--scope SCOPE]
                       [--valid]

options:
  -h, --help            show this help message and exit
  --collected COLLECTED
                        Path to collected JSON
  --namespace NAMESPACE
                        Filter namespace
  --action ACTION       Filter a specific action (will ignore --namespace if specified)
  --scope SCOPE         scope to use, default is "/" can be for example users, devices, /oid1, "/oid1,/oid2"
  --valid               Only test actions where default result is not invalidAction
```

It is possible to focus on a namespace or a specific action.

The generated CSV output also compare the result with the default permissions of a user in a default newly generated tenant with no additional rights.

**Examples:**

Check all permissions of the user
```
entraperm check --valid                                                 
```

Check if user can read bitlocker keys on all devices
```
entraperm check --action "microsoft.directory/bitlockerKeys/key/read" --scope devices
```