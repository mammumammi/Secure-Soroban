import subprocess
import json
import sys
import os
import time
import requests
import glob
from datetime import datetime

# ── Configuration ──────────────────────────────────────────
OLLAMA_URL             = "http://localhost:11434/api/generate"
MODEL                  = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
CONTRACT_ID            = os.environ.get("CONTRACT_ID", "")
TOKEN_ID               = os.environ.get("TOKEN_ID", "")
VICTIM                 = os.environ.get("VICTIM_ADDRESS", "")
ATTACKER               = os.environ.get("ATTACKER_ADDRESS", "")
VICTIM_SECRET          = os.environ.get("VICTIM_SECRET", "")
ATTACKER_SECRET        = os.environ.get("ATTACKER_SECRET", "")
NETWORK                = os.environ.get("STELLAR_NETWORK", "testnet")
CONTRACT_NAME          = os.environ.get("CONTRACT_NAME", "")
CONTRACT_DIR           = os.environ.get("CONTRACT_DIR", ".")
CONTRACTS_PATH         = os.environ.get("CONTRACTS_PATH", os.path.join(CONTRACT_DIR, "src"))
RECOVERY_TIMEOUT       = 100
TEST_AMOUNT            = 100
XLM_PRICE              = 0.12
MIN_STROOP             = 0.0000001

# ── Helper ─────────────────────────────────────────────────
def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def xlm_to_str(xlm_float):
    if xlm_float == int(xlm_float):
        return str(int(xlm_float))
    return f"{xlm_float:.7f}".rstrip('0').rstrip('.')

def substitute_placeholders(template):
    """Replace <PLACEHOLDER> tokens the AI may produce with real values."""
    return (template
        .replace("<ATTACKER>", ATTACKER)
        .replace("<VICTIM>",   VICTIM)
        .replace("<TOKEN>",    TOKEN_ID)
        .replace("<AMOUNT>",   str(TEST_AMOUNT))
        .replace("<CONTRACT>", CONTRACT_ID))

# ── Read contract source ────────────────────────────────────
def read_contract_source():
    print("\n[*] Reading contract source code...")
    sources = {}
    rs_files = glob.glob(f"{CONTRACTS_PATH}/**/src/lib.rs", recursive=True)
    for filepath in rs_files:
        contract_name = filepath.split("/")[-3]
        with open(filepath, "r") as f:
            sources[contract_name] = f.read()
        print(f"[+] Loaded: {contract_name}")
    return sources

# ── AI analysis ─────────────────────────────────────────────
def ai_analyze_contract(contract_name, source_code):
    print(f"\n[*] AI Agent analyzing {contract_name}...")
    max_chars = 8000
    truncated = source_code[:max_chars]
    if len(source_code) > max_chars:
        truncated += "\n\n[... contract truncated for analysis ...]"

    prompt = f"""You are an expert Soroban smart contract security researcher.

IMPORTANT SOROBAN-SPECIFIC FACTS:
- Soroban does NOT have reentrancy vulnerabilities — cross-contract calls are synchronous
- Soroban DOES have these real vulnerabilities:
  1. Missing require_auth() on functions that move funds
  2. Integer overflow with unchecked arithmetic
  3. Unchecked unwrap() that can panic
  4. Storage exhaustion attacks
  5. Unauthorized admin functions with no ownership check
  6. Incorrect expiration/timelock logic
  7. Missing balance checks before transfers

CRITICAL RULES:
- Do NOT flag reentrancy
- You MUST look at the ACTUAL function signatures in the source code
- "cli_args" must EXACTLY match the parameter names the function declares (e.g. if it takes `to: Address`, use `--to <ATTACKER>`)
- If a function takes no arguments, set cli_args to ""
- If setup requires calling a function first (like deposit/initialize), fill setup_function and setup_cli_args; otherwise set both to null
- Use these placeholders in cli_args: <ATTACKER>, <VICTIM>, <TOKEN>, <AMOUNT>
- If the contract has a deposit or initialize function, ALWAYS use it as setup_function to fund the contract before attacking
- For withdraw attacks, setup_function should be "deposit" with setup_cli_args "--from <VICTIM> --token <TOKEN> --amount <AMOUNT>"
- For payment-channel initialize, use "--sender <VICTIM> --recipient <ATTACKER> --token <TOKEN> --allowance <AMOUNT> --expiration null"
- For integer overflow attacks involving a fee percent, ensure you pass both `--amount <AMOUNT>` and `--fee_percent 1`
- Any argument of type Option<T> should be passed as `null` for None or the bare value (e.g. `10`) for Some.

Contract name: {contract_name}
```rust
{truncated}
```

Respond ONLY with this exact JSON (no markdown, no explanation):
{{
    "vulnerability_found": true,
    "vulnerability_type": "specific soroban vulnerability name",
    "vulnerable_function": "exact function name from source",
    "attack_description": "one sentence exploit description",
    "severity": "CRITICAL",
    "estimated_loss_xlm": 100,
    "fix": "one line fix",
    "attack_params": {{
        "function_to_call": "exact function name",
        "cli_args": "--param1 <ATTACKER> --param2 <AMOUNT>",
        "setup_function": "name of function to call first to deposit funds, or null if not needed",
    "setup_cli_args": "exact cli args for setup function replacing params with placeholders, or null"
    }}
}}"""

    for attempt in range(1, 4):
        try:
            print(f"[*] AI request attempt {attempt}/3...")
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 600}
                },
                timeout=300
            )
            if response.status_code == 200:
                raw = response.json()["response"].strip()
                print(f"[+] AI response received")
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(raw[start:end])
            print(f"[-] AI request failed: HTTP {response.status_code}")
            return None
        except requests.exceptions.Timeout:
            print(f"[-] Attempt {attempt} timed out — {'retrying' if attempt < 3 else 'giving up'}")
            time.sleep(10)
        except Exception as e:
            print(f"[-] AI agent error: {e}")
            return None
    return None

# ── Get balance ─────────────────────────────────────────────
def get_balance():
    # To check how much a contract holds, we query the token contract
    cmd = f"""stellar contract invoke \
        --id {TOKEN_ID} \
        --source {VICTIM_SECRET} \
        --network {NETWORK} \
        -- balance \
        --id {CONTRACT_ID}"""
    out, err, code = run(cmd)
    try:
        # It usually outputs something like: 
        # ℹ️  Simulation identified as read-only.....
        # "100"
        lines = out.strip().split('\n')
        val = lines[-1].replace('"', '').strip()
        return int(val)
    except:
        return 0

# ── Fund victim wallet before each attack ──────────────────
def fund_victim_wallet(amount=None):
    """Ensure the victim wallet has XLM (for fees) and tokens before each attack."""
    if amount is None:
        amount = TEST_AMOUNT

    print(f"[*] Funding victim wallet with {amount} tokens before attack...")

    # 1) Top-up victim XLM for fees via Stellar friendbot (testnet only)
    #    No stellar CLI flags needed — uses the requests lib already imported
    if NETWORK == "testnet":
        try:
            resp = requests.get(
                f"https://friendbot.stellar.org?addr={VICTIM}",
                timeout=30
            )
            if resp.status_code == 200:
                print(f"[+] Funded victim with XLM via friendbot")
            else:
                print(f"[!] Friendbot: {resp.status_code} (victim likely already has XLM)")
        except Exception as e:
            print(f"[!] Friendbot request failed: {e}")
    else:
        print(f"[!] Non-testnet — XLM top-up skipped (fund victim manually)")

    # 2) Transfer tokens attacker → victim
    #    v27: --send=yes is a top-level flag BEFORE '--', not a contract function arg
    if TOKEN_ID:
        transfer_cmd = f"""stellar contract invoke \
            --id {TOKEN_ID} \
            --source {ATTACKER_SECRET} \
            --network {NETWORK} \
            --send=yes \
            -- transfer \
            --from {ATTACKER} \
            --to {VICTIM} \
            --amount {amount}"""
        out, err, code = run(transfer_cmd)
        if code == 0:
            print(f"[+] Transferred {amount} tokens from attacker to victim")
        else:
            print(f"[!] Token transfer skipped: {err[:150]}")



# ── Execute AI attack ───────────────────────────────────────
def deploy_contract(contract_name):
    """Find and deploy the wasm for a given contract name."""
    # Search for the wasm file
    wasm_patterns = [
        f"vulnerable_contracts/escrow/target/wasm32v1-none/release/{contract_name.replace('-','_')}.wasm",
        f"target/wasm32v1-none/release/{contract_name.replace('-','_')}.wasm",
    ]
    
    wasm_path = None
    for pattern in wasm_patterns:
        matches = glob.glob(pattern)
        if matches:
            wasm_path = matches[0]
            break
    
    if not wasm_path:
        print(f"[-] No wasm found for {contract_name} — trying to build...")
        build_cmd = f"cd vulnerable_contracts/escrow && stellar contract build 2>/dev/null"
        run(build_cmd)
        for pattern in wasm_patterns:
            matches = glob.glob(pattern)
            if matches:
                wasm_path = matches[0]
                break
    
    if not wasm_path:
        print(f"[-] Could not find wasm for {contract_name} — skipping deployment")
        return None
    
    print(f"[*] Deploying {contract_name} from {wasm_path}...")
    cmd = f"""stellar contract deploy \
        --wasm {wasm_path} \
        --source {VICTIM_SECRET} \
        --network {NETWORK}"""
    
    out, err, code = run(cmd)
    if code == 0 and out.strip().startswith("C"):
        print(f"[+] Deployed: {out.strip()}")
        return out.strip()
    else:
        print(f"[-] Deploy failed: {err[:200]}")
        return None


def execute_ai_attack(analysis, contract_name):
    global CONTRACT_ID
    
    if not analysis or not analysis.get("vulnerability_found"):
        print("[*] AI found no vulnerability to exploit")
        return False, 0

    print(f"\n[*] AI identified: {analysis['vulnerability_type']}")
    print(f"[*] Executing attack on: {analysis['vulnerable_function']}")
    print(f"[*] Attack plan: {analysis['attack_description']}")

    # Deploy contract if no CONTRACT_ID set
    if not CONTRACT_ID:
        deployed_id = deploy_contract(contract_name)
        if deployed_id:
            CONTRACT_ID = deployed_id
        else:
            print(f"[-] Could not deploy {contract_name} — skipping attack")
            return False, 0

    # ── Fund victim wallet before every attack ──────────────
    fund_victim_wallet(TEST_AMOUNT)

    params        = analysis.get("attack_params", {})
    func          = params.get("function_to_call", "withdraw")
    cli_args      = substitute_placeholders(params.get("cli_args") or "")
    setup_func    = params.get("setup_function")
    setup_cli_raw = params.get("setup_cli_args")

    # Optional setup step
    if setup_func and setup_func not in ["null", None] and setup_cli_raw and setup_cli_raw not in ["null", None]:
        setup_args = substitute_placeholders(setup_cli_raw)
        print(f"\n[*] Setup: calling {setup_func} as victim...")
        setup_cmd = f"""stellar contract invoke \
            --id {CONTRACT_ID} \
            --source {VICTIM_SECRET} \
            --network {NETWORK} \
            -- {setup_func} {setup_args}"""
        out, err, code = run(setup_cmd)
        if code != 0:
            print(f"[-] Setup step failed: {err[:200]}")
            print(f"[*] Continuing anyway")
        else:
            print(f"[+] Setup complete")
    else:
        print(f"[*] No setup step needed")

    balance_before = get_balance()
    print(f"[*] Balance before attack: {balance_before}")

    print(f"\n[*] AI Agent executing: {func} {cli_args}")
    attack_cmd = f"""stellar contract invoke \
        --id {CONTRACT_ID} \
        --source {ATTACKER_SECRET} \
        --network {NETWORK} \
        -- {func} {cli_args}"""

    out, err, code = run(attack_cmd)
    attack_succeeded = code == 0

    balance_after = get_balance()
    drained = max(0, balance_before - balance_after)
    print(f"[*] Balance after attack: {balance_after}")

    if attack_succeeded and drained > 0:
        print(f"\n[!] ATTACK SUCCEEDED — {drained} XLM drained")
    elif attack_succeeded:
        print(f"\n[~] Attack call succeeded but no funds moved")
    else:
        print(f"\n[*] Attack blocked — {err[:200] if err else 'no error details'}")

    # Reset CONTRACT_ID for next contract
    CONTRACT_ID = os.environ.get("CONTRACT_ID", "")
    
    return attack_succeeded and drained > 0, drained
# ── Recover funds ───────────────────────────────────────────
def recover_funds(amount_tokens):
    print(f"\n[*] Executing fund recovery — returning {amount_tokens} tokens to victim...")

    if amount_tokens <= 0:
        print(f"[-] Nothing to recover")
        return

    if not TOKEN_ID:
        print(f"[-] TOKEN_ID not set — cannot recover tokens")
        return

    # v27: use stellar contract invoke --send=yes (before '--') to transfer
    # tokens from attacker back to victim — same pattern as fund_victim_wallet
    recover_cmd = f"""stellar contract invoke \
        --id {TOKEN_ID} \
        --source {ATTACKER_SECRET} \
        --network {NETWORK} \
        --send=yes \
        -- transfer \
        --from {ATTACKER} \
        --to {VICTIM} \
        --amount {int(amount_tokens)}"""

    out, err, code = run(recover_cmd)

    if code == 0:
        print(f"[+] RECOVERY SUCCESSFUL — {amount_tokens} tokens returned to victim")
        try:
            with open("scripts/recovery_task.json", "r") as f:
                task = json.load(f)
            task["status"] = "completed"
            task["completed_at"] = datetime.now().isoformat()
            with open("scripts/recovery_task.json", "w") as f:
                json.dump(task, f, indent=2)
        except:
            pass
    else:
        print(f"[-] Recovery failed: {err[:200]}")
        print(f"[-] Manual recovery needed: send {amount_tokens} tokens to {VICTIM}")

# ── Schedule fund recovery ──────────────────────────────────
def schedule_fund_recovery(drained_amount):
    if drained_amount <= 0:
        return
    print(f"\n[*] Scheduling fund recovery in {RECOVERY_TIMEOUT} seconds...")
    print(f"[*] {drained_amount} XLM will be returned to victim account")
    print(f"[*] This is a security simulation — funds are always returned")

    recovery_task = {
        "scheduled_at": datetime.now().isoformat(),
        "recover_at": datetime.fromtimestamp(time.time() + RECOVERY_TIMEOUT).isoformat(),
        "amount_xlm": drained_amount,
        "from_secret": ATTACKER_SECRET,
        "to_address": VICTIM,
        "network": NETWORK,
        "status": "pending"
    }
    with open("scripts/recovery_task.json", "w") as f:
        json.dump(recovery_task, f, indent=2)
    print(f"[+] Recovery task saved to scripts/recovery_task.json")

    print(f"\n[*] Waiting {RECOVERY_TIMEOUT} seconds before returning funds...")
    for remaining in range(RECOVERY_TIMEOUT, 0, -30):
        print(f"    Recovery in {remaining} seconds...")
        time.sleep(30)

    recover_funds(drained_amount)

# ── Generate AI report ──────────────────────────────────────
def generate_ai_report(analyses, attack_results):
    total_loss = sum(r.get("drained", 0) * XLM_PRICE for r in attack_results.values())
    any_critical = any(
        a.get("severity") in ["CRITICAL", "HIGH"]
        for a in analyses.values() if a
    )

    print("\n")
    print("=" * 60)
    print("   SECURESOROBAN — AI AGENT SECURITY REPORT")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"   Model Used : {MODEL}")
    print(f"   Mode       : Autonomous Attack Simulation")
    print("=" * 60)

    for contract_name, analysis in analyses.items():
        if not analysis:
            print(f"\n   [SKIP] {contract_name} — AI analysis failed")
            continue
        result = attack_results.get(contract_name, {})
        succeeded = result.get("succeeded", False)
        drained   = result.get("drained", 0)

        if analysis.get("vulnerability_found") and succeeded:
            print(f"\n   [AI-CRITICAL] {contract_name}")
            print(f"   Type     : {analysis['vulnerability_type']}")
            print(f"   Function : {analysis['vulnerable_function']}")
            print(f"   Attack   : {analysis['attack_description']}")
            print(f"   Drained  : {drained} XLM (${drained * XLM_PRICE:.2f} USD)")
            print(f"   Fix      : {analysis['fix']}")
        elif analysis.get("vulnerability_found"):
            print(f"\n   [AI-FOUND] {contract_name} — vulnerability identified, attack did not drain funds")
            print(f"   Type     : {analysis['vulnerability_type']}")
            print(f"   Severity : {analysis['severity']}")
            print(f"   Fix      : {analysis.get('fix', 'N/A')}")
        else:
            print(f"\n   [AI-PASS] {contract_name} — no vulnerability found")

    print("\n" + "=" * 60)
    print(f"   TOTAL AI-IDENTIFIED LOSS: ${total_loss:.2f} USD")
    print(f"   PUSH STATUS: {'BLOCKED' if any_critical else 'SAFE'}")
    print("=" * 60)

    report = {
        "timestamp": datetime.now().isoformat(),
        "model": MODEL,
        "mode": "ai_agent_attack",
        "total_loss_usd": round(total_loss, 2),
        "push_blocked": any_critical,
        "analyses": analyses,
        "attack_results": attack_results,
    }
    with open("scripts/ai_agent_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("\n   Report saved to scripts/ai_agent_report.json")
    return any_critical

# ── Main ────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Secure Soroban — AI Agent Attacker Starting...")
    print(f"Model: {MODEL}")
    print("=" * 60)

    sources = read_contract_source()
    if not sources:
        print("[-] No contract source files found")
        sys.exit(1)

    analyses      = {}
    attack_results = {}
    total_drained  = 0

    target_contract = CONTRACT_NAME.strip() or None
    if target_contract:
        print(f"[*] Targeting contract from env: {target_contract}")
    else:
        print(f"[*] No CONTRACT_NAME set — scanning all discovered contracts")

    ordered = []
    if target_contract and target_contract in sources:
        ordered.append(target_contract)
    ordered += [n for n in sources if n != target_contract]

    for name in ordered:
        analysis = ai_analyze_contract(name, sources[name])
        analyses[name] = analysis

        if analysis:
            print(f"\n[*] AI Analysis Result for {name}:")
            print(f"    Vulnerability : {analysis.get('vulnerability_type', 'None')}")
            print(f"    Severity      : {analysis.get('severity', 'None')}")
            print(f"    Attack Plan   : {analysis.get('attack_description', 'None')}")
            print(f"    Function      : {analysis.get('attack_params', {}).get('function_to_call', 'N/A')}")
            print(f"    CLI Args      : {analysis.get('attack_params', {}).get('cli_args', 'N/A')}")

            succeeded, drained = execute_ai_attack(analysis, name)  # ← pass name
            attack_results[name] = {"succeeded": succeeded, "drained": drained}
            total_drained += drained
        else:
            attack_results[name] = {"succeeded": False, "drained": 0}

    blocked = generate_ai_report(analyses, attack_results)

    if total_drained > 0:
        schedule_fund_recovery(total_drained)

    sys.exit(1 if blocked else 0)